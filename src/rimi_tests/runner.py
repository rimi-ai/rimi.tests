"""Execution: plan, run, record. Arrives with the engine (step T2).

The runner turns validated cases into a plan (variants x runs x models), executes it
with bounded parallelism, and writes one chained record per call through
`proof.ChainLog`, inside `runs/<date>/proof-bundle/`. Nothing is rewritten: a run that
is interrupted is resumed, never restarted in place.

What a record carries (specification §13.2): hash of the full request, hash of the raw
response, model and version returned by the provider, parameters, tokens, timestamp,
and the hash of the previous record. Never an API key.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .loader import Case
from .proof import bundle_paths


@dataclass(frozen=True)
class Execution:
    """One model call to make: a case, one variant, one run index, one model."""

    case: Case
    variant_index: int
    run_index: int
    model: str


def run_directory(root: str | Path = "runs", day: date | None = None) -> Path:
    """runs/<YYYY-MM-DD>/ — the directory a campaign writes into."""
    return Path(root) / (day or date.today()).isoformat()


def bundle_for(root: str | Path = "runs", day: date | None = None) -> dict[str, Path]:
    """Where the proof bundle of that run lives."""
    return bundle_paths(run_directory(root, day))


def build_plan(*_args, **_kwargs):
    raise NotImplementedError("the execution plan arrives with step T2")


def execute(*_args, **_kwargs):
    raise NotImplementedError("execution arrives with step T2")
