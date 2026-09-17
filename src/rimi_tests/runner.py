"""Execution: plan, run, record.

The runner turns validated cases into a plan (variants x runs x models), executes it
with bounded parallelism, and writes one chained record per call — inside
`runs/<date>/proof-bundle/`, in append-only JSONL. Nothing is ever rewritten: an
interrupted campaign is resumed, never restarted in place.

What a record carries (specification §13.2): hash of the full request, hash of the raw
response, model and version returned by the provider, parameters, tokens, timestamp,
and the hash of the previous record. Never an API key.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from . import checks, providers
from .cache import Cache, fingerprint
from .loader import Case
from .proof import ChainLog, bundle_paths, sha256_canonical, sha256_text

RESULTS_FILE = "results.jsonl"
PROOF_MANIFEST = Path("proof-bundle") / "manifest.json"


@dataclass(frozen=True)
class Execution:
    """One model call to make: a case, one variant, one run index, one model."""

    case: Case
    variant_index: int
    run_index: int
    model: providers.ModelSpec

    @property
    def key(self) -> str:
        """Stable identity of this call, used to resume without doing it twice."""
        return f"{self.case.rule}/{self.case.id}#v{self.variant_index}r{self.run_index}@{self.model.name}"

    @property
    def variant(self) -> str | None:
        variants = self.case.variants
        return variants[self.variant_index] if variants else None


def run_directory(root: str | Path = "runs", day: date | None = None, *,
                  unique: bool = False, resume: bool = False) -> Path:
    """runs/<YYYY-MM-DD>/ — the directory a campaign writes into.

    Two campaigns on the same day must not share a directory: the manifest of the
    first one would be overwritten, and its chain would grow with calls it never
    announced. `unique=True` therefore falls back to <date>-2, <date>-3… while
    `resume=True` reopens the most recent one.
    """
    base = Path(root) / (day or datetime.now(UTC).date()).isoformat()
    if resume:
        siblings = sorted(p for p in base.parent.glob(base.name + "*") if p.is_dir())
        return siblings[-1] if siblings else base
    if unique:
        candidate, index = base, 1
        while (candidate / PROOF_MANIFEST).exists():
            index += 1
            candidate = base.with_name(f"{base.name}-{index}")
        return candidate
    return base


def bundle_for(root: str | Path = "runs", day: date | None = None) -> dict[str, Path]:
    """Where the proof bundle of that run lives."""
    return bundle_paths(run_directory(root, day))


def build_plan(cases: list[Case], models: list[providers.ModelSpec], *,
               variants: int | None = None, runs: int | None = None) -> list[Execution]:
    """Every call the profile asks for, in a stable order."""
    plan: list[Execution] = []
    for case in cases:
        count = len(case.variants) or 1
        if variants:
            count = min(count, variants)
        for variant_index in range(count):
            for run_index in range(runs or case.runs):
                for model in models:
                    plan.append(Execution(case, variant_index, run_index, model))
    return plan


def build_messages(case: Case, variant: str | None) -> list[dict[str, Any]]:
    """The conversation as the model sees it, with tool results simulated.

    A `tool_result` turn becomes the pair a provider expects: an assistant message
    asking for the tool, then the tool answer. Nothing is ever really called.
    """
    messages: list[dict[str, Any]] = [{"role": "system", "content": case.data["system_prompt"]}]
    turns = list(case.data["turns"])
    last_user = max((i for i, t in enumerate(turns) if t["role"] == "user"), default=None)
    for position, turn in enumerate(turns):
        role = turn["role"]
        if role == "user":
            content = variant if (variant and position == last_user) else turn["content"]
            messages.append({"role": "user", "content": content})
        elif role == "assistant":
            messages.append({"role": "assistant", "content": turn["content"]})
        else:
            call_id = f"call_{position}"
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": call_id, "type": "function",
                                "function": {"name": turn["tool"], "arguments": "{}"}}],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": turn["tool"],
                "content": json.dumps(turn["content"], ensure_ascii=False),
            })
    return messages


def source_numbers(case: Case, variant: str | None) -> list:
    """Numbers the case itself puts in front of the model: anything else is invented."""
    text = " ".join(
        json.dumps(t["content"], ensure_ascii=False) if t["role"] == "tool_result"
        else str(t.get("content", ""))
        for t in case.data["turns"]
    )
    if variant:
        text += " " + variant
    text += " " + case.data["system_prompt"]
    return checks.numbers_in(text)


def _resolve_tool_schema(reference: str, case_path: Path) -> dict[str, Any] | None:
    for candidate in [Path(reference), *(p / reference for p in case_path.resolve().parents[:4])]:
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return None


@dataclass
class RunSummary:
    """What a run leaves in memory; the full report comes with step T3."""

    run_dir: Path
    results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: int = 0
    cache_stats: dict[str, int] = field(default_factory=dict)
    expected: int = 0

    @property
    def realised(self) -> int:
        return len(self.results)

    def pass_rate(self) -> float:
        decided = [r for r in self.results if r["passed"] is not None]
        return (sum(1 for r in decided if r["passed"]) / len(decided)) if decided else 0.0

    def by_case_and_model(self) -> dict[tuple[str, str], tuple[int, int]]:
        table: dict[tuple[str, str], list[int]] = {}
        for result in self.results:
            key = (result["case"], result["model"])
            counters = table.setdefault(key, [0, 0])
            counters[1] += 1
            counters[0] += 1 if result["passed"] else 0
        return {k: (v[0], v[1]) for k, v in table.items()}

    def cost(self, billed_only: bool = False) -> float:
        """What the calls cost. `billed_only` leaves out what the cache served for free."""
        return sum(r.get("cost") or 0.0 for r in self.results
                   if not (billed_only and r.get("from_cache")))


def execute(plan: list[Execution], *, out: str | Path = "runs", cache: Cache | None = None,
            workers: int = 4, resume: bool = False, day: date | None = None,
            directory: Path | None = None, call: Any = None) -> RunSummary:
    """Run the plan, recording every call in the chained log.

    `call` lets a test pass a fake provider: the runner never imports network code itself.
    """
    cache = cache or Cache(enabled=True)
    caller = call or providers.complete
    directory = directory or run_directory(out, day)
    paths = bundle_paths(directory)
    paths["raw"].mkdir(parents=True, exist_ok=True)
    chain = ChainLog(paths["chain"])
    results_path = directory / RESULTS_FILE

    done: set[str] = set()
    if resume:
        done = {record.get("execution") for record in chain.records() if record.get("execution")}

    summary = RunSummary(run_dir=directory, expected=len(plan))
    lock = Lock()

    def one(execution: Execution) -> None:
        if execution.key in done:
            with lock:
                summary.skipped += 1
            return
        case = execution.case
        variant = execution.variant
        messages = build_messages(case, variant)
        # The case declares the parameters it wants; models.yaml may override them,
        # because that is where a model's own constraints are declared (some models
        # accept only temperature=1). The record keeps what was actually sent.
        case_params = {k: v for k, v in (case.data.get("params") or {}).items()
                       if k in {"temperature", "top_p", "max_tokens"}}
        params = {**case_params, **execution.model.params}
        tools = providers.tool_definitions(
            case.data.get("tools", []), lambda ref: _resolve_tool_schema(ref, case.path))
        key = fingerprint(messages, params, execution.model.litellm_id)

        cached = cache.get(key)
        if cached is not None:
            completion = providers.Completion(**cached)
            from_cache = True
        else:
            try:
                completion = caller(messages, execution.model, params, tools)
            except providers.ProviderError as exc:
                with lock:
                    summary.errors.append(f"{execution.key}: {exc}")
                return
            cache.put(key, completion)
            from_cache = False

        context = checks.CheckContext(
            response_text=completion.text,
            language=case.language,
            tool_calls=completion.tool_calls,
            source_numbers=source_numbers(case, variant),
        )
        verdicts = checks.evaluate_all(case.expected_checks, context)
        passed = checks.verdict(verdicts)

        transcript = {
            "execution": execution.key,
            **case.identity(),
            "variant_index": execution.variant_index,
            "variant": variant,
            "run_index": execution.run_index,
            "model": execution.model.name,
            "messages": messages,
            "response": completion.text,
            "tool_calls": completion.tool_calls,
            "checks": verdicts,
            "passed": passed,
        }
        raw_name = f"{sha256_text(execution.key)[:16]}.json"
        (paths["raw"] / raw_name).write_text(
            json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")

        record = {
            "execution": execution.key,
            **case.identity(),
            "model": execution.model.name,
            "model_returned": completion.model_returned,
            "params": params,
            "request_sha256": sha256_canonical(messages),
            "response_sha256": sha256_text(completion.text),
            "transcript_file": raw_name,
            "tokens": completion.usage,
            "latency_ms": completion.latency_ms,
            "finish_reason": completion.finish_reason,
            "answered_with_tool_call": bool(completion.tool_calls) and not completion.text.strip(),
            "from_cache": from_cache,
            "passed": passed,
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        cost = providers.price(execution.model, completion.usage["input"], completion.usage["output"])
        if cost is not None:
            record["cost_usd"] = round(cost, 6)

        with lock:
            chain.append(record)
            summary.results.append({
                "case": f"{case.rule}/{case.id}",
                "answered_with_tool_call": bool(completion.tool_calls) and not completion.text.strip(),
                "model": execution.model.name,
                "variant_index": execution.variant_index,
                "run_index": execution.run_index,
                "passed": passed,
                "checks": verdicts,
                "response": completion.text,
                "cost": cost,
                "from_cache": from_cache,
            })
            with results_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(summary.results[-1], ensure_ascii=False) + "\n")

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        list(pool.map(one, plan))

    summary.cache_stats = cache.stats()
    return summary


def failure_excerpt(text: str, width: int = 160) -> str:
    """One line of a failing answer, for the console."""
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed[:width] + ("…" if len(collapsed) > width else "")
