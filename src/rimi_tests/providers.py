"""Model access through LiteLLM. Arrives with the engine (step T2).

One interface, the user's own API keys, read from the environment and never written
anywhere. `models.yaml` lists provider, model, version and parameters; every call
records the model and version the provider actually returned, the parameters, the
tokens (input, output, cache) and the latency.

Rate limits are respected, parallelism is bounded, and an interrupted campaign is
resumed with `--resume`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    """A model as declared in models.yaml."""

    name: str          # identifier used in reports, e.g. "claude-sonnet-4-5"
    litellm_id: str    # identifier passed to LiteLLM, e.g. "anthropic/claude-sonnet-4-5"
    provider: str
    params: dict | None = None


def load_models(*_args, **_kwargs):
    raise NotImplementedError("reading models.yaml arrives with step T2")


def complete(*_args, **_kwargs):
    raise NotImplementedError("model calls arrive with step T2")
