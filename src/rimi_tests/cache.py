"""Cache by fingerprint. Arrives with the engine (step T2).

Key: hash of (prompt, parameters, model). Re-running a report does not pay for the
calls again; `--no-cache` forces them. The cache stores responses, never keys.
"""

from __future__ import annotations

from pathlib import Path

from .proof import sha256_canonical

CACHE_DIR = Path(".cache/rimi")


def fingerprint(prompt: list[dict], params: dict, model: str) -> str:
    """The cache key — also the value a chained record refers to."""
    return sha256_canonical({"prompt": prompt, "params": params, "model": model})


def get(*_args, **_kwargs):
    raise NotImplementedError("the cache arrives with step T2")


def put(*_args, **_kwargs):
    raise NotImplementedError("the cache arrives with step T2")
