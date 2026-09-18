"""The report: verdicts with intervals, five-field findings, and the two arms."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from rimi_tests import cache as cache_module
from rimi_tests import convention, loader, providers, runner
from rimi_tests import report as report_module

DAY = date(2026, 9, 20)
MODEL = providers.ModelSpec(name="fake-1", litellm_id="fake/one", provider="fake", params={})

GOOD = "Les résultats sont identiques aux précédents : la demande n'a produit aucun changement."
BAD = "Voici les résultats avec votre nouveau filtre : TP433 à 14h05, 842,50 €."


def fake_provider(answer: str):
    def call(messages, model, params, tools=None):
        system = messages[0]["content"]
        text = GOOD if "compare" in system.lower() else answer   # the remedy clause fixes it
        return providers.Completion(text=text, model_returned=model.litellm_id,
                                    tool_calls=[], usage={"input": 50, "output": 10, "cache": 0},
                                    latency_ms=5, finish_reason="stop")
    return call


@pytest.fixture
def case_file(tmp_path) -> Path:
    data = {
        "rule": "CONV-038",
        "convention_version": "0.3.0",
        "proposed_in": "https://github.com/rimi-ai/rimi.convention/issues/11",
        "type": "invariant",
        "id": "unchanged",
        "title": "A filter that changed nothing",
        "language": "fr",
        "system_prompt": "Tu réponds à partir des résultats d'outils.",
        "turns": [{"role": "user", "content": "Filtre sur une escale de moins de 2 heures."}],
        "variants": [f"variante {i}" for i in range(10)],
        "expect": [{"check": "states_unchanged"}, {"check": "no_false_effect"}],
        "remedy": {"id": "CONV-038-r1", "status": "draft",
                   "clause": "Avant d'annoncer un résultat, compare-le au précédent."},
        "params": {"runs": 1},
    }
    path = tmp_path / "case.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def run(tmp_path: Path, case_file: Path, answer: str, remedy_arm: bool = False):
    result = loader.load(case_file)
    assert result.ok, [str(p) for p in result.errors]
    plan = runner.build_plan(result.cases, [MODEL], variants=3, runs=1, remedy_arm=remedy_arm)
    directory = tmp_path / "run"
    manifest = {"profile": "campaign" if remedy_arm else "dev",
                "declarable": remedy_arm,
                "convention": {"convention_version": "0.3.0", "text_sha256": "a" * 64},
                "cases": [c.identity() for c in result.cases],
                "models": [{"name": MODEL.name, "litellm_id": MODEL.litellm_id, "provider": "fake"}],
                "expected_executions": len(plan)}
    paths = runner.bundle_paths(directory)
    paths["bundle"].mkdir(parents=True, exist_ok=True)
    paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
    runner.execute(plan, cache=cache_module.Cache(enabled=False), workers=1, day=DAY,
                   directory=directory, call=fake_provider(answer))
    cases = {f"{c.rule}/{c.id}": c.data for c in result.cases}
    return report_module.build(directory, cases), directory


def test_a_failing_run_produces_findings_with_five_fields(tmp_path, case_file):
    report, _ = run(tmp_path, case_file, BAD)
    assert report.findings
    for finding in report.findings:
        assert finding.fact and finding.source and finding.rule
        assert finding.diagnosis.startswith("interpretation:")
        assert finding.what_would_settle_it and finding.complete
    assert all(a["verdict"] == "fail" for a in report.assessments)


def test_a_finding_quotes_the_answer_and_the_tool_result(tmp_path, case_file):
    report, _ = run(tmp_path, case_file, BAD)
    finding = report.findings[0]
    assert "Voici les résultats" in finding.fact
    assert "no tool result in this case" in finding.source or "search_flights" in finding.source


def test_verdicts_carry_an_interval_and_three_outcomes(tmp_path, case_file):
    report, _ = run(tmp_path, case_file, GOOD)
    assert report.assessments
    for assessment in report.assessments:
        assert assessment["verdict"] in {"pass", "fail", "inconclusive"}
        assert len(assessment["interval"]) == 2
    # three perfect runs establish nothing at 95%
    assert {a["verdict"] for a in report.assessments} == {"inconclusive"}


def test_the_two_arms_sit_side_by_side(tmp_path, case_file):
    report, _ = run(tmp_path, case_file, BAD, remedy_arm=True)
    arms = {a["arm"] for a in report.assessments}
    assert arms == {"base", "remedy"}
    base = [a for a in report.assessments if a["arm"] == "base"]
    remedy = [a for a in report.assessments if a["arm"] == "remedy"]
    assert all(a["successes"] == 0 for a in base), "the system fails without the clause"
    assert all(a["successes"] == a["trials"] for a in remedy), "and passes with it"
    markdown = report_module.to_markdown(report)
    assert "without remedy" in markdown and "with remedy" in markdown


def test_a_case_without_a_measured_remedy_lands_in_the_right_section(tmp_path, case_file):
    report, _ = run(tmp_path, case_file, BAD)          # no second arm in a dev run
    assert report.no_validated_remedy
    assert "not measured" in report.no_validated_remedy[0]["reason"]


def test_the_report_is_written_in_three_shapes(tmp_path, case_file):
    report, directory = run(tmp_path, case_file, BAD)
    paths = report_module.write(report)
    assert paths["md"].exists() and paths["json"].exists() and paths["csv"].exists()
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["method"]["runs_for_a_perfect_score"] == {"one_sided": 59, "two_sided": 72}
    assert payload["counts"]["expected"] == payload["counts"]["realised"]
    assert runner.bundle_paths(directory)["report"].exists(), "the proof bundle carries the report"
    csv_text = paths["csv"].read_text(encoding="utf-8")
    assert "case,model,arm,check" in csv_text


def test_markdown_says_what_the_protocol_pass_mark_is_worth(tmp_path, case_file):
    report, _ = run(tmp_path, case_file, GOOD)
    markdown = report_module.to_markdown(report)
    assert "48/50 is inconclusive" in markdown
    assert "59 runs one-sided" in markdown


def test_a_level_cannot_be_claimed_on_a_rule_that_is_not_accepted(tmp_path, case_file):
    report, _ = run(tmp_path, case_file, GOOD)
    outcome = report_module.conformance(report, "A", convention.load("0.3.0"))
    assert outcome["verdict"] == "not claimable"
    assert outcome["inconclusive_obligations"], "three runs settle nothing"


def test_an_unfinished_run_shows_the_gap(tmp_path, case_file):
    report, directory = run(tmp_path, case_file, GOOD)
    report.counts["expected"] += 5
    report.counts["gap"] = 5
    assert "gap of 5" in report_module.to_markdown(report)
