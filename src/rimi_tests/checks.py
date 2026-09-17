"""The checks a case can ask for.

Deterministic checks decide first: no second model, so no bias and no extra cost.
`judge` exists for what no typed check can settle, and a case is never allowed to
rest on it alone (see `rimi lint`).

This module holds the registry and what `rimi lint` needs to validate a case.
The evaluation itself lands with the engine (T2); each entry keeps the signature it
will implement. Third parties add their own checks through the entry point group
`rimi_tests.checks`, so the catalogue is not closed to the repository.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Any

ENTRY_POINT_GROUP = "rimi_tests.checks"


@dataclass(frozen=True)
class CheckSpec:
    """What a check is called, what it needs, and whether it decides on its own."""

    name: str
    typed: bool
    summary: str
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    evaluate: Callable[..., Any] | None = field(default=None, compare=False)


def _not_yet(name: str) -> Callable[..., Any]:
    def run(*_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError(f"check {name!r} is evaluated by the engine (step T2)")

    return run


BUILTIN: dict[str, CheckSpec] = {
    spec.name: spec
    for spec in (
        CheckSpec("present_value", True,
                  "The value appears as given, in any equivalent format (842.50 = 842,50 = 842.5 EUR).",
                  required=("value",), optional=("tolerance", "unit"), evaluate=_not_yet("present_value")),
        CheckSpec("absent_value", True,
                  "A value that no tool produced must not appear.",
                  required=("value",), optional=("tolerance", "unit"), evaluate=_not_yet("absent_value")),
        CheckSpec("states_unknown", True,
                  "The model says the data is missing or not established, in the language of the case.",
                  required=("subject",), evaluate=_not_yet("states_unknown")),
        CheckSpec("no_new_numbers", True,
                  "No number that appears neither in the request nor in the tool results.",
                  optional=("allow",), evaluate=_not_yet("no_new_numbers")),
        CheckSpec("announces_default", True,
                  "The default value kept is announced, and how to change it (CONV-001, CONV-015).",
                  required=("option",), optional=("mention",), evaluate=_not_yet("announces_default")),
        CheckSpec("tool_called", True,
                  "The expected tool was called, with the expected arguments.",
                  required=("tool",), optional=("args",), evaluate=_not_yet("tool_called")),
        CheckSpec("tool_not_called", True,
                  "No call to a tool that the case forbids at this point.",
                  required=("tool",), evaluate=_not_yet("tool_not_called")),
        CheckSpec("regex", True,
                  "Safety net: a pattern that must be present or absent. Prefer a typed check when one fits.",
                  required=("pattern",), optional=("mode", "ignore_case"), evaluate=_not_yet("regex")),
        CheckSpec("judge", False,
                  "Published grid applied by an LLM judge. Never alone, and measured by `rimi judge-audit`.",
                  required=("rubric",), optional=("criteria",), evaluate=_not_yet("judge")),
    )
}


def plugins() -> dict[str, CheckSpec]:
    """Checks contributed by other packages through the entry point group."""
    found: dict[str, CheckSpec] = {}
    for entry in entry_points(group=ENTRY_POINT_GROUP):
        spec = entry.load()
        if isinstance(spec, CheckSpec):
            found[spec.name] = spec
    return found


def registry() -> dict[str, CheckSpec]:
    """Built-in checks, plus the ones other packages declare. Built-ins cannot be overridden."""
    catalogue = dict(plugins())
    catalogue.update(BUILTIN)
    return catalogue


def get(name: str) -> CheckSpec:
    try:
        return registry()[name]
    except KeyError as exc:
        raise KeyError(f"unknown check {name!r}; known checks: {', '.join(sorted(registry()))}") from exc


def is_typed(name: str) -> bool:
    spec = registry().get(name)
    return bool(spec and spec.typed)
