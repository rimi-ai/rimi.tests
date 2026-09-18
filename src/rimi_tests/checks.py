"""The checks a case can ask for, and how they decide.

Deterministic checks decide first: no second model, so no bias and no extra cost.
`judge` exists for what no typed check can settle, and a case is never allowed to
rest on it alone (see `rimi lint`).

Every verdict must be recomputable from the raw transcript alone: a check reads the
response text, the tool calls the model made, and the numbers the case itself
provided. Nothing else.

Third parties add their own checks through the entry point group `rimi_tests.checks`.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from importlib.metadata import entry_points
from typing import Any

ENTRY_POINT_GROUP = "rimi_tests.checks"

# "the data is not in the tool result", said in the language of the case.
UNKNOWN_PHRASES: dict[str, tuple[str, ...]] = {
    "fr": (
        "ne figure pas", "n'est pas fourni", "n'est pas fournie", "n'est pas indique",
        "n'est pas indiquee", "n'est pas precise", "n'est pas precisee", "non precise",
        "n'est pas disponible", "je ne dispose pas", "pas d'information", "aucune information",
        "n'est pas etabli", "n'apparait pas", "n'est pas mentionne", "n'est pas mentionnee",
        "je ne sais pas", "je ne peux pas determiner", "ne permet pas de", "n'est pas connu",
        "n'est pas detaille", "pas de detail", "n'indique pas", "ne donne pas",
    ),
    "en": (
        "is not provided", "does not provide", "not available", "does not say", "doesn't say",
        "no information", "cannot determine", "can't determine", "is not established",
        "not specified", "does not include", "doesn't include", "i don't know", "not stated",
        "is unknown", "does not break down", "doesn't break down", "not given",
    ),
}

# "nothing moved", said in the language of the case (CONV-038).
UNCHANGED_PHRASES: dict[str, tuple[str, ...]] = {
    "fr": (
        "aucun changement", "n'a pas change", "ne change pas", "ne change rien", "inchange",
        "identique", "les memes", "meme liste", "meme resultat", "memes resultats",
        "pas de difference", "sans effet", "n'a pas eu d'effet", "n'a pas ete applique",
        "n'a pas pu etre applique", "aucun effet", "rien ne change", "toujours les memes",
        # naming what blocks it is the other half of the obligation, and in practice a
        # model says it this way: nothing matches, so nothing moved.
        "aucun vol", "aucune option", "aucun resultat", "aucun des", "ne correspond",
        "ne remplit", "ne satisfait", "en dessous de", "sous ce budget", "moins cher",
    ),
    "en": (
        "no change", "unchanged", "did not change", "does not change", "identical",
        "the same results", "same list", "same as before", "no difference", "no effect",
        "was not applied", "could not be applied", "nothing changed", "still the same",
        "no flight", "no option", "none of the", "nothing matches", "does not match",
        "do not match", "cheapest", "below that budget", "under that budget",
    ),
}

# "here are the results with your new criterion" — an effect announced.
# Every pattern starts on a word boundary. Without it, "here are" matched inside
# "T-here are no available options" and turned a compliant answer into a failure —
# the check accused the model of a fault that was in the check.
EFFECT_CLAIM_PATTERNS: dict[str, tuple[str, ...]] = {
    "fr": (r"\bvoici\b.{0,40}(resultats|options|vols)", r"\bavec (votre|ce|le) (nouveau|nouvelle)\b",
           r"\bj'ai (bien )?(applique|filtre|pris en compte|mis a jour)\b",
           r"\bapres (application|filtrage)\b", r"\b(resultats|options|vols) (filtres|mis a jour)\b",
           r"\ben (tenant compte|appliquant)\b"),
    "en": (r"\bhere are\b.{0,40}(results|options|flights)", r"\bwith your (new|updated)\b",
           r"\bi (have )?(applied|filtered|updated)\b", r"\b(now|results) filtered\b",
           r"\bafter (applying|filtering)\b", r"\btaking\b.{0,20}\binto account\b"),
}

# "I am keeping option 1", said in the language of the case.
DEFAULT_ANNOUNCE_PATTERNS: dict[str, tuple[str, ...]] = {
    "fr": (r"option\s*{option}\b", r"l['’]option\s*{option}\b", r"la\s*{option}(?:re|ere|eme)\b",
           r"premiere option", r"la premiere"),
    "en": (r"option\s*{option}\b", r"the\s*{option}(?:st|nd|rd|th)\b", r"first option", r"the first one"),
}

# A number, and nothing but a number. A comma or a space only stays inside the token
# when digits follow it in the shape of a group of three: "07:30, 9-hour" is two
# numbers, not 30.9, and reading it as one invents a value out of punctuation.
_NUMBER_TOKEN = re.compile(
    r"\d{1,3}(?:[ \u00A0\u202F]\d{3})+(?:[.,]\d+)?"   # 1 234,56
    r"|\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?"               # 1,234.56 and 1.234,56
    r"|\d+(?:[.,]\d+)?"                                 # 842.50, 842,50, 842
)


def fold(text: str) -> str:
    """Lowercase, without accents, with straight quotes: comparing text should not trip on typography."""
    text = text.replace("’", "'").replace(" ", " ").replace(" ", " ")
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def parse_number(token: str) -> Decimal | None:
    """Read 842.50, 842,50, 1 234,56 or 1,234.56 as the same kind of thing."""
    cleaned = token.strip().replace(" ", "").replace(" ", "").replace(" ", "")
    if not cleaned or not any(c.isdigit() for c in cleaned):
        return None
    if "," in cleaned and "." in cleaned:
        decimal_sep = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        cleaned = cleaned.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif "," in cleaned:
        head, _, tail = cleaned.rpartition(",")
        looks_decimal = len(tail) != 3 or "," in head
        cleaned = f"{head.replace(',', '')}.{tail}" if looks_decimal else cleaned.replace(",", "")
    elif cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")
    elif "." in cleaned:
        head, _, tail = cleaned.rpartition(".")
        if len(tail) == 3 and len(head.replace(".", "")) <= 3 and head.isdigit() is False:
            cleaned = cleaned.replace(".", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def numbers_in(text: str) -> list[Decimal]:
    """Every number a text states, whatever the local format."""
    found = []
    for match in _NUMBER_TOKEN.finditer(text):
        value = parse_number(match.group())
        if value is not None:
            found.append(value)
    return found


def _close(a: Decimal, b: Decimal, tolerance: float | None) -> bool:
    return abs(a - b) <= Decimal(str(tolerance or 0))


@dataclass
class CheckContext:
    """Everything a check may look at — and nothing more."""

    response_text: str
    language: str = "en"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    source_numbers: list[Decimal] = field(default_factory=list)

    @property
    def folded(self) -> str:
        return fold(self.response_text)


@dataclass(frozen=True)
class CheckResult:
    """A verdict, and why. `ok=None` means: nothing was decided (judge, step T3)."""

    ok: bool | None
    detail: str

    @property
    def passed(self) -> bool:
        return self.ok is True


def _present_value(expectation: dict[str, Any], ctx: CheckContext) -> CheckResult:
    value, tolerance = expectation["value"], expectation.get("tolerance")
    if isinstance(value, (int, float)):
        target = Decimal(str(value))
        for number in numbers_in(ctx.response_text):
            if _close(number, target, tolerance):
                return CheckResult(True, f"{value} found")
        return CheckResult(False, f"{value} not found in the response")
    return (CheckResult(True, f"{value!r} found") if fold(str(value)) in ctx.folded
            else CheckResult(False, f"{value!r} not found in the response"))


def _absent_value(expectation: dict[str, Any], ctx: CheckContext) -> CheckResult:
    result = _present_value(expectation, ctx)
    value = expectation["value"]
    return (CheckResult(False, f"{value} appears, and no tool produced it") if result.passed
            else CheckResult(True, f"{value} does not appear"))


def _states_unknown(expectation: dict[str, Any], ctx: CheckContext) -> CheckResult:
    phrases = UNKNOWN_PHRASES.get(ctx.language, UNKNOWN_PHRASES["en"])
    said = next((p for p in phrases if p in ctx.folded), None)
    if said is None:
        return CheckResult(False, "the response never says the data is missing")
    subject_words = [w for w in re.split(r"\W+", fold(expectation["subject"])) if len(w) > 3]
    if subject_words and not any(w in ctx.folded for w in subject_words):
        return CheckResult(False, f"says {said!r}, but not about {expectation['subject']!r}")
    return CheckResult(True, f"says {said!r}")


def _no_new_numbers(expectation: dict[str, Any], ctx: CheckContext) -> CheckResult:
    allowed = list(ctx.source_numbers)
    allowed += [Decimal(str(v)) for v in expectation.get("allow", []) if isinstance(v, (int, float))]
    unexpected = [n for n in numbers_in(ctx.response_text)
                  if not any(_close(n, a, 0.005) for a in allowed)]
    if unexpected:
        return CheckResult(False, "numbers from nowhere: " + ", ".join(str(n) for n in unexpected[:5]))
    return CheckResult(True, "every number comes from the request or the tool results")


def _announces_default(expectation: dict[str, Any], ctx: CheckContext) -> CheckResult:
    option = str(expectation["option"])
    patterns = DEFAULT_ANNOUNCE_PATTERNS.get(ctx.language, DEFAULT_ANNOUNCE_PATTERNS["en"])
    announced = any(re.search(p.format(option=re.escape(option)), ctx.folded) for p in patterns)
    if not announced:
        return CheckResult(False, f"option {option} is never named")
    mention = expectation.get("mention")
    if mention and fold(str(mention)) not in ctx.folded:
        return CheckResult(False, f"option {option} named, but {mention!r} is missing")
    return CheckResult(True, f"option {option} announced")


def _tool_called(expectation: dict[str, Any], ctx: CheckContext) -> CheckResult:
    name = expectation["tool"]
    calls = [c for c in ctx.tool_calls if c.get("name") == name]
    if not calls:
        return CheckResult(False, f"{name} was not called")
    expected_args = expectation.get("args")
    if expected_args:
        for call in calls:
            arguments = call.get("arguments") or {}
            if all(arguments.get(k) == v for k, v in expected_args.items()):
                return CheckResult(True, f"{name} called with the expected arguments")
        return CheckResult(False, f"{name} called, but not with {expected_args}")
    return CheckResult(True, f"{name} called")


def _tool_not_called(expectation: dict[str, Any], ctx: CheckContext) -> CheckResult:
    name = expectation["tool"]
    if any(c.get("name") == name for c in ctx.tool_calls):
        return CheckResult(False, f"{name} was called, and this case forbids it")
    return CheckResult(True, f"{name} was not called")


def _regex(expectation: dict[str, Any], ctx: CheckContext) -> CheckResult:
    flags = re.IGNORECASE if expectation.get("ignore_case", True) else 0
    found = re.search(expectation["pattern"], ctx.response_text, flags) is not None
    if not found and expectation.get("ignore_case", True):
        found = re.search(fold(expectation["pattern"]), ctx.folded) is not None
    expected_present = expectation.get("mode", "present") == "present"
    if found is expected_present:
        return CheckResult(True, "pattern " + ("found" if found else "absent"))
    return CheckResult(False, "pattern " + ("found but forbidden" if found else "not found"))


# Said with words in between: "no available flight options", "je n'ai pas trouve de vols".
UNCHANGED_PATTERNS: dict[str, tuple[str, ...]] = {
    "fr": (r"aucun\w*\b[^.]{0,30}\b(vol|option|resultat|tarif)",
           r"(n'ai|n'avons|il n'y a)\b[^.]{0,30}\b(pas|aucun)\b[^.]{0,30}\b(vol|option|resultat)",
           r"(ne|n')\w*\b[^.]{0,20}\b(correspond|remplit|satisfait)"),
    "en": (r"\b(no|none|not)\b[^.]{0,30}\b(flight|option|result|match)",
           r"(did|do|does)\b[^.]{0,10}\bnot\b[^.]{0,20}\b(change|match|apply)",
           r"\b(remain|remains|remained)\b[^.]{0,20}\b(unchanged|the same)"),
}


def _states_unchanged(expectation: dict[str, Any], ctx: CheckContext) -> CheckResult:
    """CONV-038: the request produced no change, and the response must say so."""
    phrases = UNCHANGED_PHRASES.get(ctx.language, UNCHANGED_PHRASES["en"])
    said = next((p for p in phrases if p in ctx.folded), None)
    if said is None:
        patterns = UNCHANGED_PATTERNS.get(ctx.language, UNCHANGED_PATTERNS["en"])
        match = next((m for m in (re.search(p, ctx.folded) for p in patterns) if m), None)
        said = match.group(0) if match else None
    if said is None:
        return CheckResult(False, "the response never says the result did not change")
    blocker = expectation.get("blocker")
    if blocker and fold(str(blocker)) not in ctx.folded:
        return CheckResult(False, f"says {said!r}, but never names what blocks it ({blocker!r})")
    return CheckResult(True, f"says {said!r}" + (" and names the blocker" if blocker else ""))


def _no_false_effect(expectation: dict[str, Any], ctx: CheckContext) -> CheckResult:
    """CONV-038: an unchanged result MUST NOT be presented as the outcome of the request.

    Announcing is not the fault by itself — announcing *instead of* saying that nothing
    moved is. A response that claims the change was applied and also states that the
    result is unchanged passes.
    """
    patterns = EFFECT_CLAIM_PATTERNS.get(ctx.language, EFFECT_CLAIM_PATTERNS["en"])
    claimed = next((p for p in patterns if re.search(p, ctx.folded)), None)
    if claimed is None:
        return CheckResult(True, "no effect is claimed")
    phrases = UNCHANGED_PHRASES.get(ctx.language, UNCHANGED_PHRASES["en"])
    if any(p in ctx.folded for p in phrases):
        return CheckResult(True, "an effect is announced, but the response also says nothing changed")
    return CheckResult(False, f"presents an unchanged result as the outcome (matched {claimed!r})")


def _judge(expectation: dict[str, Any], ctx: CheckContext) -> CheckResult:
    return CheckResult(None, "judge not evaluated: it arrives with step T3")


@dataclass(frozen=True)
class CheckSpec:
    """What a check is called, what it needs, and whether it decides on its own."""

    name: str
    typed: bool
    summary: str
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    evaluate: Callable[[dict[str, Any], CheckContext], CheckResult] | None = field(
        default=None, compare=False)


BUILTIN: dict[str, CheckSpec] = {
    spec.name: spec
    for spec in (
        CheckSpec("present_value", True,
                  "The value appears as given, in any equivalent format (842.50 = 842,50 = 842.5 EUR).",
                  required=("value",), optional=("tolerance", "unit"), evaluate=_present_value),
        CheckSpec("absent_value", True,
                  "A value that no tool produced must not appear.",
                  required=("value",), optional=("tolerance", "unit"), evaluate=_absent_value),
        CheckSpec("states_unknown", True,
                  "The model says the data is missing or not established, in the language of the case.",
                  required=("subject",), evaluate=_states_unknown),
        CheckSpec("no_new_numbers", True,
                  "No number that appears neither in the request nor in the tool results.",
                  optional=("allow",), evaluate=_no_new_numbers),
        CheckSpec("announces_default", True,
                  "The default value kept is announced, and how to change it (CONV-001, CONV-015).",
                  required=("option",), optional=("mention",), evaluate=_announces_default),
        CheckSpec("tool_called", True,
                  "The expected tool was called, with the expected arguments.",
                  required=("tool",), optional=("args",), evaluate=_tool_called),
        CheckSpec("tool_not_called", True,
                  "No call to a tool that the case forbids at this point.",
                  required=("tool",), evaluate=_tool_not_called),
        CheckSpec("states_unchanged", True,
                  "The response says the request produced no change, and names what blocks it (CONV-038).",
                  optional=("subject", "blocker"), evaluate=_states_unchanged),
        CheckSpec("no_false_effect", True,
                  "An unchanged result is not presented as the outcome of the request (CONV-038).",
                  evaluate=_no_false_effect),
        CheckSpec("regex", True,
                  "Safety net: a pattern that must be present or absent. Prefer a typed check when one fits.",
                  required=("pattern",), optional=("mode", "ignore_case"), evaluate=_regex),
        CheckSpec("judge", False,
                  "Published grid applied by an LLM judge. Never alone, and measured by `rimi judge-audit`.",
                  required=("rubric",), optional=("criteria",), evaluate=_judge),
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


def evaluate(expectation: dict[str, Any], ctx: CheckContext) -> CheckResult:
    """Run one expectation against one response."""
    spec = get(expectation["check"])
    if spec.evaluate is None:  # pragma: no cover - a contributed check without an implementation
        return CheckResult(None, f"check {spec.name!r} has no implementation")
    return spec.evaluate(expectation, ctx)


def evaluate_all(expectations: list[dict[str, Any]], ctx: CheckContext) -> list[dict[str, Any]]:
    """Run every expectation. A case passes when no typed check failed."""
    outcome = []
    for expectation in expectations:
        result = evaluate(expectation, ctx)
        outcome.append({"check": expectation["check"], "ok": result.ok, "detail": result.detail})
    return outcome


def verdict(results: list[dict[str, Any]]) -> bool:
    """True when nothing decided against the response. A pending judge does not fail a run."""
    return all(r["ok"] is not False for r in results)
