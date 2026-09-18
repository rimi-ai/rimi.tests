"""Read test cases, validate them, and hash them.

A case is a self-contained YAML file (specification §3). Loading it answers three
questions: is it well formed (JSON Schema), does it make sense against the convention
it cites (rule exists, at least one typed check), and what is its hash — the one that
goes into the manifest, the execution plan and the results.

Turning cases into an execution plan (variants x runs x models) comes with the
engine (T2); it starts from `Case.executions()`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from . import checks, convention
from .proof import sha256_bytes, sha256_canonical

CAMPAIGN_MIN_VARIANTS = 10  # test protocol of the convention


def schema_text() -> str:
    """The case schema, taken from the installed package (a copy lives in schemas/ for editors)."""
    return resources.files("rimi_tests.data").joinpath("case.schema.json").read_text(encoding="utf-8")


def _resolve_reference(reference: str, case_path: Path) -> Path | None:
    """Find a file a case points to (a tool schema), from the case or from the working directory."""
    candidates = [Path(reference), *(parent / reference for parent in case_path.resolve().parents[:4])]
    return next((c for c in candidates if c.exists()), None)


class CaseError(Exception):
    """A case cannot be read or does not hold together."""


@dataclass(frozen=True)
class Problem:
    """Something `rimi lint` has to say about a case."""

    path: Path
    severity: str  # "error" | "warning"
    message: str
    where: str = ""

    def __str__(self) -> str:
        location = f" [{self.where}]" if self.where else ""
        return f"{self.path}{location}: {self.message}"


@dataclass(frozen=True)
class Case:
    path: Path
    data: dict[str, Any]
    case_sha256: str
    rule_sha256: str | None = None

    @property
    def rule(self) -> str:
        return self.data["rule"]

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def convention_version(self) -> str:
        return self.data["convention_version"]

    @property
    def language(self) -> str:
        return self.data["language"]

    @property
    def variants(self) -> list[str]:
        return list(self.data.get("variants") or [])

    @property
    def runs(self) -> int:
        return int((self.data.get("params") or {}).get("runs", 1))

    @property
    def expected_checks(self) -> list[dict[str, Any]]:
        return list(self.data["expect"])

    def executions(self, models: list[str], runs: int | None = None,
                   variants: int | None = None) -> int:
        """How many model calls this case represents. Used by `rimi estimate` (T2)."""
        variant_count = min(len(self.variants) or 1, variants or len(self.variants) or 1)
        return variant_count * (runs or self.runs) * max(len(models), 1)

    def identity(self) -> dict[str, str]:
        """What every record about this case carries, so a result can be traced back."""
        return {
            "case": f"{self.rule}/{self.id}",
            "case_sha256": self.case_sha256,
            "rule": self.rule,
            "rule_sha256": self.rule_sha256 or "",
            "convention_version": self.convention_version,
        }


def _schema_validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(schema_text()))


def read_case(path: str | Path) -> Case:
    """Read one YAML case and hash it. Raises `CaseError` if the file is unusable."""
    path = Path(path)
    raw = path.read_bytes()
    try:
        data = yaml.safe_load(raw.decode("utf-8"))
    except yaml.YAMLError as exc:
        raise CaseError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise CaseError(f"{path}: a case must be a YAML mapping")
    return Case(path=path, data=data, case_sha256=sha256_bytes(raw))


def discover(root: str | Path) -> list[Path]:
    """Every case file under `root`, in a stable order."""
    root = Path(root)
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob("*.y*ml") if p.is_file())


def validate(case: Case, *, strict_variants: bool = False) -> tuple[Case, list[Problem]]:
    """Schema, then meaning. Returns the case (with its rule hash) and what is wrong with it."""
    problems: list[Problem] = []
    validator = _schema_validator()
    for error in sorted(validator.iter_errors(case.data), key=lambda e: list(e.path)):
        where = "/".join(str(p) for p in error.path) or "(root)"
        problems.append(Problem(case.path, "error", error.message, where))
    if problems:
        return case, problems

    rule_sha256 = None
    try:
        index = convention.load(case.convention_version)
    except convention.ConventionNotAvailableError as exc:
        problems.append(Problem(case.path, "error", str(exc), "convention_version"))
    else:
        if not index.has(case.rule):
            proposed = case.data.get("proposed_in")
            if proposed:
                # A rule needs a real case and a test case before it can be Proposed:
                # a case therefore exists before its rule, and says where it is discussed.
                problems.append(Problem(case.path, "warning",
                                        f"rule {case.rule} is not in convention {index.version}; "
                                        f"proposed in {proposed}", "rule"))
            else:
                problems.append(Problem(case.path, "error",
                                        f"rule {case.rule} does not exist in convention "
                                        f"{index.version}", "rule"))
        else:
            rule = index.rule(case.rule)
            rule_sha256 = rule.sha256
            declared, actual = case.data["type"], rule.type
            if actual and declared != actual and declared != rule.also:
                problems.append(Problem(case.path, "warning",
                                        f"case says type {declared!r}, convention says {actual!r}", "type"))
            if rule.part != "A":
                problems.append(Problem(case.path, "warning",
                                        f"{case.rule} belongs to part {rule.part}; v1 runs behaviour cases "
                                        "of part A only", "rule"))

    names = [c["check"] for c in case.expected_checks]
    for index_of, name in enumerate(names):
        spec = checks.registry().get(name)
        if spec is None:
            problems.append(Problem(case.path, "error", f"unknown check {name!r}", f"expect/{index_of}"))
            continue
        missing = [p for p in spec.required if p not in case.expected_checks[index_of]]
        if missing:
            problems.append(Problem(case.path, "error",
                                    f"check {name!r} needs {', '.join(missing)}", f"expect/{index_of}"))
    if not any(checks.is_typed(n) for n in names):
        problems.append(Problem(case.path, "error",
                                "at least one typed check is required; `judge` alone is not enough",
                                "expect"))

    declared_tools = {t["name"] for t in case.data.get("tools", [])}
    for position, turn in enumerate(case.data["turns"]):
        tool = turn.get("tool")
        if tool and tool not in declared_tools:
            problems.append(Problem(case.path, "error",
                                    f"turn {position} uses tool {tool!r}, which the case does not declare",
                                    f"turns/{position}"))
    for position, expectation in enumerate(case.expected_checks):
        tool = expectation.get("tool")
        if tool and tool not in declared_tools:
            problems.append(Problem(case.path, "error",
                                    f"check on tool {tool!r}, which the case does not declare",
                                    f"expect/{position}"))

    variants = case.variants
    if not variants:
        problems.append(Problem(case.path, "warning",
                                "no variant: the last user turn is used as is", "variants"))
    elif len(variants) < CAMPAIGN_MIN_VARIANTS:
        severity = "error" if strict_variants else "warning"
        problems.append(Problem(case.path, severity,
                                f"{len(variants)} variants; a campaign asks for at least "
                                f"{CAMPAIGN_MIN_VARIANTS}", "variants"))

    for tool in case.data.get("tools", []):
        reference = tool.get("schema")
        if reference and _resolve_reference(reference, case.path) is None:
            problems.append(Problem(case.path, "error",
                                    f"tool schema not found: {reference}", "tools"))

    return Case(path=case.path, data=case.data, case_sha256=case.case_sha256,
                rule_sha256=rule_sha256), problems


@dataclass
class LoadResult:
    cases: list[Case] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    @property
    def errors(self) -> list[Problem]:
        return [p for p in self.problems if p.severity == "error"]

    @property
    def warnings(self) -> list[Problem]:
        return [p for p in self.problems if p.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def fingerprint(self) -> str:
        """One hash for the whole set: what the manifest of a campaign pins (T8)."""
        return sha256_canonical(sorted(c.case_sha256 for c in self.cases))


def load(root: str | Path, *, strict_variants: bool = False) -> LoadResult:
    """Read and validate every case under `root`."""
    result = LoadResult()
    seen: dict[tuple[str, str], Path] = {}
    for path in discover(root):
        try:
            case = read_case(path)
        except CaseError as exc:
            result.problems.append(Problem(path, "error", str(exc)))
            continue
        case, problems = validate(case, strict_variants=strict_variants)
        result.problems.extend(problems)
        if not any(p.severity == "error" for p in problems):
            key = (case.rule, case.id)
            if key in seen:
                result.problems.append(Problem(path, "error",
                                               f"case id {case.id!r} already used by {seen[key]}", "id"))
                continue
            seen[key] = path
            result.cases.append(case)
    result.cases.sort(key=lambda c: (c.rule, c.id))
    return result
