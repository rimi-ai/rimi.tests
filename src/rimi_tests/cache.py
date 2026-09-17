"""Cache by fingerprint: re-reading a report must not pay for the calls again.

Key: hash of (messages, parameters, model). The cache stores what a provider answered,
never a key and never a header. `--no-cache` forces real calls.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .proof import sha256_canonical

DEFAULT_CACHE_DIR = Path(".cache/rimi")


def fingerprint(messages: list[dict[str, Any]], params: dict[str, Any], model: str) -> str:
    """The cache key — also what a chained record points to."""
    return sha256_canonical({"messages": messages, "params": params, "model": model})


class Cache:
    """A directory of JSON files, one per fingerprint."""

    def __init__(self, directory: str | Path = DEFAULT_CACHE_DIR, enabled: bool = True) -> None:
        self.directory = Path(directory)
        self.enabled = enabled
        self.hits = 0
        self.misses = 0

    def _path(self, key: str) -> Path:
        return self.directory / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        path = self._path(key)
        if not path.exists():
            self.misses += 1
            return None
        self.hits += 1
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        payload = asdict(value) if hasattr(value, "__dataclass_fields__") else value
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses}
