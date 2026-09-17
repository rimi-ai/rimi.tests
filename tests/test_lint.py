"""What `rimi lint` must refuse, and what it must only warn about."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from rimi_tests import loader
from rimi_tests.cli import main

CASES = Path(__file__).resolve().parents[1] / "cases"


def write(tmp_path: Path, data: dict, name: str = "case.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture
def case() -> dict:
    return {
        "rule": "CONV-002",
        "convention_version": "0.3.0",
        "type": "invariant",
        "id": "minimal",
        "title": "A minimal but valid case",
        "language": "fr",
        "system_prompt": "Tu réponds à partir des résultats d'outils.",
        "turns": [{"role": "user", "content": "Combien par personne ?"}],
        "expect": [{"check": "states_unknown", "subject": "prix par passager"}],
        "variants": [f"variante {i}" for i in range(10)],
        "params": {"runs": 1},
    }


def errors_of(tmp_path: Path, case: dict, **kwargs) -> list[str]:
    write(tmp_path, case)
    return [p.message for p in loader.load(tmp_path, **kwargs).errors]


def test_a_valid_case_passes(tmp_path, case):
    assert errors_of(tmp_path, case) == []


def test_unknown_rule_is_refused(tmp_path, case):
    case["rule"] = "CONV-999"
    assert any("does not exist" in m for m in errors_of(tmp_path, case))


def test_unknown_convention_version_is_refused(tmp_path, case):
    case["convention_version"] = "9.9.9"
    assert any("no convention projection" in m for m in errors_of(tmp_path, case))


def test_a_case_needs_at_least_one_typed_check(tmp_path, case):
    case["expect"] = [{"check": "judge", "rubric": "Did the model invent a per-passenger price?"}]
    assert any("typed check" in m for m in errors_of(tmp_path, case))


def test_judge_is_allowed_next_to_a_typed_check(tmp_path, case):
    case["expect"].append({"check": "judge", "rubric": "Is the wording clear?"})
    assert errors_of(tmp_path, case) == []


def test_unknown_check_is_refused(tmp_path, case):
    case["expect"] = [{"check": "vibes"}]
    assert any("is not one of" in m or "unknown check" in m for m in errors_of(tmp_path, case))


def test_missing_required_field_is_refused(tmp_path, case):
    del case["title"]
    assert any("title" in m for m in errors_of(tmp_path, case))


def test_check_missing_its_parameter_is_refused(tmp_path, case):
    case["expect"] = [{"check": "present_value"}]
    assert errors_of(tmp_path, case) != []


def test_tool_used_but_not_declared_is_refused(tmp_path, case):
    case["turns"].append({"role": "tool_result", "tool": "search_flights", "content": {"total": 1}})
    assert any("does not declare" in m for m in errors_of(tmp_path, case))


def test_missing_tool_schema_file_is_refused(tmp_path, case):
    case["tools"] = [{"name": "search_flights", "schema": "schemas/nope.json"}]
    assert any("tool schema not found" in m for m in errors_of(tmp_path, case))


def test_too_few_variants_warns_and_can_be_made_strict(tmp_path, case):
    case["variants"] = ["a", "b"]
    write(tmp_path, case)
    result = loader.load(tmp_path)
    assert result.ok and any("at least 10" in p.message for p in result.warnings)
    assert not loader.load(tmp_path, strict_variants=True).ok


def test_type_mismatch_only_warns(tmp_path, case):
    case["type"] = "informative"
    write(tmp_path, case)
    result = loader.load(tmp_path)
    assert result.ok
    assert any("convention says" in p.message for p in result.warnings)


def test_cli_lint_accepts_the_sample_cases():
    result = CliRunner().invoke(main, ["lint", str(CASES)])
    assert result.exit_code == 0, result.output
    assert "ok" in result.output


def test_cli_lint_exits_1_on_error(tmp_path, case):
    case["rule"] = "CONV-999"
    write(tmp_path, case)
    result = CliRunner().invoke(main, ["lint", str(tmp_path)])
    assert result.exit_code == 1


def test_cli_planned_commands_exit_2():
    for command in (["run"], ["estimate"], ["verify", "runs/x"]):
        result = CliRunner().invoke(main, command)
        assert result.exit_code == 2, command


def test_cli_checks_lists_the_catalogue():
    result = CliRunner().invoke(main, ["checks"])
    assert result.exit_code == 0
    for name in ("present_value", "states_unknown", "judge"):
        assert name in result.output
