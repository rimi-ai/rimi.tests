"""The convention seen from the runner: which rules exist, in which version.

The text is the source. This module reads a machine-readable projection of it.
Today that projection is built locally from the published `en.md` and shipped with
the package (`data/convention-<version>.json`). It is replaced by the signed
`convention.json` published by rimi.convention at each release (task R06), and then
pinned by `rimi.lock` (T2): the engine refuses to run cases written against another
version.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

from .proof import sha256_canonical

DATA_PACKAGE = "rimi_tests.data"


class ConventionNotAvailableError(LookupError):
    """No projection of the convention is bundled for that version."""


@dataclass(frozen=True)
class Rule:
    id: str
    part: str
    type: str | None
    wave: int | None
    status: str
    summary: str
    principle: str | None = None
    audience: str | None = None
    also: str | None = None

    @property
    def sha256(self) -> str:
        """Hash of the rule as published: goes into the plan and into the results."""
        return sha256_canonical({
            "id": self.id, "part": self.part, "type": self.type, "also": self.also,
            "wave": self.wave, "status": self.status, "summary": self.summary,
        })


@dataclass(frozen=True)
class Convention:
    version: str
    text_sha256: str
    source: dict[str, Any]
    rules: dict[str, Rule]
    thresholds: dict[str, float]

    def has(self, rule_id: str) -> bool:
        return rule_id in self.rules

    def rule(self, rule_id: str) -> Rule:
        if rule_id not in self.rules:
            raise KeyError(rule_id)
        return self.rules[rule_id]

    def wave(self, number: int) -> list[Rule]:
        return [r for r in self.rules.values() if r.wave == number]


def _from_mapping(payload: dict[str, Any]) -> Convention:
    rules = {}
    for raw in payload["rules"]:
        rules[raw["id"]] = Rule(
            id=raw["id"], part=raw["part"], type=raw.get("type"), wave=raw.get("wave"),
            status=raw.get("status", "draft"), summary=raw.get("summary", ""),
            principle=raw.get("principle"), audience=raw.get("audience"), also=raw.get("also"),
        )
    return Convention(
        version=payload["convention_version"],
        text_sha256=payload.get("source", {}).get("text_sha256", ""),
        source=payload.get("source", {}),
        rules=rules,
        thresholds=payload.get("thresholds", {"must": 0.95, "should": 0.80}),
    )


@cache
def load(version: str) -> Convention:
    """Load the bundled projection for `version` (e.g. "0.3.0")."""
    name = f"convention-{version}.json"
    try:
        text = resources.files(DATA_PACKAGE).joinpath(name).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise ConventionNotAvailableError(
            f"no convention projection for version {version}; available: {', '.join(available()) or 'none'}"
        ) from exc
    return _from_mapping(json.loads(text))


def load_file(path: str | Path) -> Convention:
    """Load a projection from disk, e.g. a convention.json downloaded from a release."""
    return _from_mapping(json.loads(Path(path).read_text(encoding="utf-8")))


def available() -> list[str]:
    versions = []
    for entry in resources.files(DATA_PACKAGE).iterdir():
        name = entry.name
        if name.startswith("convention-") and name.endswith(".json"):
            versions.append(name[len("convention-"):-len(".json")])
    return sorted(versions)


LOCK_FILE = "rimi.lock"


def read_lock(path: str | Path = LOCK_FILE) -> dict[str, Any] | None:
    """The pinned version, if there is one. A user's verdict never moves on its own."""
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_lock(version: str, path: str | Path = LOCK_FILE) -> dict[str, Any]:
    """Pin a version: what `rimi run` checks the cases against."""
    index = load(version)
    lock = {
        "convention_version": index.version,
        "text_sha256": index.text_sha256,
        "source": index.source,
        "pinned_by": "rimi-tests",
    }
    Path(path).write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return lock


class VersionMismatchError(RuntimeError):
    """Cases and lock disagree: mixing two versions is refused, not averaged."""


def check_versions(case_versions: set[str], path: str | Path = LOCK_FILE) -> dict[str, Any]:
    """Refuse to run when the cases do not all cite the pinned version."""
    if len(case_versions) > 1:
        raise VersionMismatchError(
            "cases cite several versions of the convention: " + ", ".join(sorted(case_versions))
        )
    version = next(iter(case_versions))
    lock = read_lock(path)
    if lock is None:
        return write_lock(version, path)
    if lock["convention_version"] != version:
        raise VersionMismatchError(
            f"cases cite convention {version}, but {path} pins {lock['convention_version']}; "
            f"run `rimi convention update --version {version}` to move the pin on purpose"
        )
    return lock
