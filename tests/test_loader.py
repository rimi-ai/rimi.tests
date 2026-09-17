"""Loader and schema. No model is ever called here."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rimi_tests import convention, loader

CASES = Path(__file__).resolve().parents[1] / "cases"


def write_case(tmp_path: Path, data: dict, name: str = "case.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture
def valid_case() -> dict:
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
        "params": {"runs": 1},
    }


def test_sample_cases_load_and_validate():
    result = loader.load(CASES)
    assert result.ok, [str(p) for p in result.errors]
    assert {c.rule for c in result.cases} == {"CONV-001", "CONV-002"}
    for case in result.cases:
        assert len(case.variants) >= loader.CAMPAIGN_MIN_VARIANTS
        assert len(case.case_sha256) == 64
        assert case.rule_sha256, "a validated case carries the hash of its rule"


def test_case_hash_is_stable_and_follows_the_bytes(tmp_path, valid_case):
    path = write_case(tmp_path, valid_case)
    first = loader.read_case(path).case_sha256
    assert first == loader.read_case(path).case_sha256
    path.write_text(path.read_text(encoding="utf-8") + "\n# a comment\n", encoding="utf-8")
    assert loader.read_case(path).case_sha256 != first


def test_identity_carries_what_a_result_needs(tmp_path, valid_case):
    case, problems = loader.validate(loader.read_case(write_case(tmp_path, valid_case)))
    assert not [p for p in problems if p.severity == "error"]
    identity = case.identity()
    assert identity["case"] == "CONV-002/minimal"
    assert identity["convention_version"] == "0.3.0"
    assert identity["rule_sha256"] == convention.load("0.3.0").rule("CONV-002").sha256


def test_executions_counts_variants_runs_and_models(tmp_path, valid_case):
    valid_case["variants"] = ["a", "b", "c", "d"]
    valid_case["params"] = {"runs": 5}
    case = loader.read_case(write_case(tmp_path, valid_case))
    assert case.executions(["m1", "m2"]) == 4 * 5 * 2
    assert case.executions(["m1"], runs=1, variants=3) == 3


def test_discover_is_sorted_and_finds_yaml(tmp_path, valid_case):
    write_case(tmp_path, valid_case, "b.yaml")
    write_case(tmp_path, valid_case, "a.yml")
    assert [p.name for p in loader.discover(tmp_path)] == ["a.yml", "b.yaml"]


def test_duplicate_case_id_is_an_error(tmp_path, valid_case):
    write_case(tmp_path, valid_case, "one.yaml")
    write_case(tmp_path, valid_case, "two.yaml")
    result = loader.load(tmp_path)
    assert not result.ok
    assert any("already used" in p.message for p in result.errors)


def test_fingerprint_changes_with_the_set(tmp_path, valid_case):
    write_case(tmp_path, valid_case, "one.yaml")
    first = loader.load(tmp_path).fingerprint()
    second = dict(valid_case, id="another")
    write_case(tmp_path, second, "two.yaml")
    assert loader.load(tmp_path).fingerprint() != first


def test_convention_index_matches_the_published_text():
    index = convention.load("0.3.0")
    assert index.version == "0.3.0"
    assert len(index.text_sha256) == 64
    assert len(index.rules) == 66            # 35 CONV + 11 CONC + 20 SOB
    assert len(index.wave(1)) == 15          # wave 1 is the core of 15 rules
    assert index.rule("CONV-001").type == "default_convention"
    assert index.rule("CONV-002").type == "invariant"


def test_unknown_convention_version_is_reported():
    with pytest.raises(convention.ConventionNotAvailableError):
        convention.load("9.9.9")
