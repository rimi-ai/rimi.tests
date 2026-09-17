"""Model access through LiteLLM: one interface, the user's own keys.

Keys are read from the environment, never from a file of this repository and never
written to a run. What a call records is the opposite: model and version as the
provider returned them, parameters, tokens, latency — everything a third party needs
to judge whether the campaign was what it claims to be.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_MODELS_FILE = "models.yaml"
# Environment variable expected by LiteLLM for each provider, for a readable error.
KEY_BY_PROVIDER = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GEMINI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


class ProviderError(RuntimeError):
    """A call could not be made, or could not be made honestly."""


@dataclass(frozen=True)
class ModelSpec:
    """A model as declared in models.yaml."""

    name: str          # what appears in a report, e.g. "claude-sonnet-5"
    litellm_id: str    # what LiteLLM expects, e.g. "anthropic/claude-sonnet-5"
    provider: str
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def key_variable(self) -> str | None:
        return KEY_BY_PROVIDER.get(self.provider)

    def key_present(self) -> bool:
        variable = self.key_variable
        return bool(variable and os.environ.get(variable))


@dataclass(frozen=True)
class Completion:
    """One answer, with what is needed to replay and to audit it."""

    text: str
    model_returned: str
    tool_calls: list[dict[str, Any]]
    usage: dict[str, int]
    latency_ms: int
    finish_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def load_models(path: str | Path = DEFAULT_MODELS_FILE) -> list[ModelSpec]:
    """Read models.yaml. Falls back to models.example.yaml so `rimi estimate` works out of the box."""
    path = Path(path)
    if not path.exists():
        example = path.with_name("models.example.yaml")
        if not example.exists():
            raise ProviderError(f"{path} not found; copy models.example.yaml to models.yaml")
        path = example
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    models = []
    for entry in data.get("models", []):
        models.append(ModelSpec(
            name=entry["name"],
            litellm_id=entry["litellm_id"],
            provider=entry.get("provider", entry["litellm_id"].split("/", 1)[0]),
            params=entry.get("params") or {},
        ))
    if not models:
        raise ProviderError(f"{path} declares no model")
    return models


def select(models: list[ModelSpec], names: list[str] | None = None, limit: int | None = None,
           require_key: bool = False) -> list[ModelSpec]:
    """Pick the models to run: by name, or the first ones of the list."""
    chosen = models
    if names:
        by_name = {m.name: m for m in models}
        missing = [n for n in names if n not in by_name]
        if missing:
            raise ProviderError(f"unknown model(s): {', '.join(missing)}")
        chosen = [by_name[n] for n in names]
    if require_key:
        chosen = [m for m in chosen if m.key_present()]
        if not chosen:
            raise ProviderError(
                "no model has its API key in the environment; "
                "export the key of at least one provider (e.g. ANTHROPIC_API_KEY)"
            )
    return chosen[:limit] if limit else chosen


def tool_definitions(case_tools: list[dict[str, Any]], resolve) -> list[dict[str, Any]]:
    """Turn the tools a case declares into the function definitions a model expects."""
    definitions = []
    for tool in case_tools or []:
        schema = tool.get("inline_schema")
        if schema is None and tool.get("schema"):
            schema = resolve(tool["schema"])
        definitions.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": (schema or {}).get("description", f"Tool {tool['name']}"),
                "parameters": {k: v for k, v in (schema or {}).items() if not k.startswith("$")}
                or {"type": "object", "properties": {}},
            },
        })
    return definitions


def complete(messages: list[dict[str, Any]], model: ModelSpec, params: dict[str, Any],
             tools: list[dict[str, Any]] | None = None, timeout: int = 120) -> Completion:
    """One call. Raises `ProviderError` with a readable reason; never logs the key."""
    import litellm  # imported late: it is heavy, and `rimi lint` does not need it

    if not model.key_present():
        raise ProviderError(f"{model.key_variable or 'the API key'} is not set for {model.name}")

    started = time.monotonic()
    try:
        response = litellm.completion(
            model=model.litellm_id,
            messages=messages,
            tools=tools or None,
            timeout=timeout,
            **params,
        )
    except Exception as exc:  # litellm raises provider-specific errors
        raise ProviderError(f"{model.name}: {type(exc).__name__}: {exc}") from exc
    latency_ms = int((time.monotonic() - started) * 1000)

    payload = response.model_dump() if hasattr(response, "model_dump") else dict(response)
    choice = (payload.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    calls = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            import json
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {"_raw": arguments}
        calls.append({"name": function.get("name"), "arguments": arguments or {}})

    usage = payload.get("usage") or {}
    return Completion(
        text=message.get("content") or "",
        model_returned=payload.get("model") or model.litellm_id,
        tool_calls=calls,
        usage={
            "input": int(usage.get("prompt_tokens") or 0),
            "output": int(usage.get("completion_tokens") or 0),
            "cache": int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0),
        },
        latency_ms=latency_ms,
        finish_reason=choice.get("finish_reason"),
        raw=payload,
    )


def price(model: ModelSpec, input_tokens: int, output_tokens: int) -> float | None:
    """What a call costs, when LiteLLM knows the price. `None` when it does not."""
    try:
        import litellm

        prompt_cost, completion_cost = litellm.cost_per_token(
            model=model.litellm_id, prompt_tokens=input_tokens, completion_tokens=output_tokens
        )
        return float(prompt_cost + completion_cost)
    except Exception:
        return None


def count_tokens(model: ModelSpec, messages: list[dict[str, Any]]) -> int | None:
    """Prompt size before paying for it. `None` when the model is unknown to LiteLLM."""
    try:
        import litellm

        return int(litellm.token_counter(model=model.litellm_id, messages=messages))
    except Exception:
        return None
