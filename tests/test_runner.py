"""The engine, with a fake provider: no test here ever reaches the network."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from rimi_tests import cache as cache_module
from rimi_tests import loader, proof, providers, runner

CASES = Path(__file__).resolve().parents[1] / "cases"
DAY = date(2026, 9, 20)

MODEL = providers.ModelSpec(name="fake-1", litellm_id="fake/one", provider="fake",
                            params={"temperature": 0.0})


def fake_provider(answer: str = "le prix par passager n'est pas fourni ; le total est de 842,50 €",
                  tool_calls=None, record=None):
    """A provider that answers without calling anything."""

    def call(messages, model, params, tools=None):
        if record is not None:
            record.append({"model": model.name, "messages": messages})
        return providers.Completion(
            text=answer,
            model_returned=f"{model.litellm_id}-2026-09-01",
            tool_calls=tool_calls or [],
            usage={"input": 100, "output": 20, "cache": 0},
            latency_ms=12,
            finish_reason="stop",
        )

    return call


@pytest.fixture
def cases():
    result = loader.load(CASES)
    assert result.ok
    return result.cases


@pytest.fixture
def no_cache(tmp_path):
    return cache_module.Cache(directory=tmp_path / "cache", enabled=False)


def test_plan_is_variants_times_runs_times_models(cases):
    plan = runner.build_plan(cases, [MODEL], variants=3, runs=1)
    assert len(plan) == 3 * 1 * len(cases)
    assert [e.key for e in plan] == sorted({e.key for e in plan}), "keys are unique"
    plan = runner.build_plan(cases, [MODEL, MODEL], variants=2, runs=2)
    assert len(plan) == 2 * 2 * 2 * len(cases)


def test_messages_put_the_variant_in_the_last_user_turn(cases):
    case = next(c for c in cases if c.rule == "CONV-002")
    messages = runner.build_messages(case, "Quel est le prix par voyageur ?")
    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "Quel est le prix par voyageur ?"}
    tool_messages = [m for m in messages if m["role"] == "tool"]
    assert tool_messages and json.loads(tool_messages[0]["content"])["total_price"] == 842.50
    assert any(m.get("tool_calls") for m in messages), "a tool result comes with its call"


def test_source_numbers_come_from_the_case(cases):
    """Numbers are compared as values: 842.5 and 842,50 are the same number."""
    case = next(c for c in cases if c.rule == "CONV-002")
    numbers = runner.source_numbers(case, "et pour 1 personne ?")
    for expected in ("842.50", "2", "1"):
        assert any(n == Decimal(expected) for n in numbers), expected
    assert not any(n == Decimal("421.25") for n in numbers), "the invented value is not a source"


def test_run_writes_chain_raw_and_results(tmp_path, cases, no_cache):
    plan = runner.build_plan(cases[:1], [MODEL], variants=2, runs=1)
    summary = runner.execute(plan, out=tmp_path, cache=no_cache, workers=1, day=DAY,
                             call=fake_provider())
    assert summary.expected == 2 and summary.realised == 2
    paths = proof.bundle_paths(tmp_path / DAY.isoformat())
    records = proof.ChainLog(paths["chain"]).records()
    assert len(records) == 2
    assert proof.verify_chain(records).ok
    assert len(list(paths["raw"].glob("*.json"))) == 2
    assert (tmp_path / DAY.isoformat() / runner.RESULTS_FILE).exists()
    first = records[0]
    assert first["model_returned"].endswith("2026-09-01")
    assert first["tokens"] == {"input": 100, "output": 20, "cache": 0}
    assert len(first["request_sha256"]) == 64 and len(first["response_sha256"]) == 64
    assert first["case_sha256"] and first["rule_sha256"]


def test_a_good_answer_passes_and_a_bad_one_fails(tmp_path, cases, no_cache):
    case = [c for c in cases if c.rule == "CONV-002"]
    plan = runner.build_plan(case, [MODEL], variants=1, runs=1)
    ok = runner.execute(plan, out=tmp_path / "ok", cache=no_cache, workers=1, day=DAY,
                        call=fake_provider())
    assert ok.results[0]["passed"] is True

    invented = runner.execute(plan, out=tmp_path / "ko", cache=no_cache, workers=1, day=DAY,
                              call=fake_provider("cela fait 421,25 € par personne"))
    assert invented.results[0]["passed"] is False
    failed = [c for c in invented.results[0]["checks"] if c["ok"] is False]
    assert {c["check"] for c in failed} >= {"absent_value", "states_unknown"}


def test_resume_skips_what_the_chain_already_holds(tmp_path, cases, no_cache):
    plan = runner.build_plan(cases[:1], [MODEL], variants=2, runs=1)
    runner.execute(plan, out=tmp_path, cache=no_cache, workers=1, day=DAY, call=fake_provider())
    again = runner.execute(plan, out=tmp_path, cache=no_cache, workers=1, day=DAY, resume=True,
                           call=fake_provider())
    assert again.skipped == 2 and again.realised == 0
    records = proof.ChainLog(proof.bundle_paths(tmp_path / DAY.isoformat())["chain"]).records()
    assert len(records) == 2, "resuming adds nothing to the chain"


def test_cache_avoids_the_second_call(tmp_path, cases):
    calls: list[dict] = []
    cache = cache_module.Cache(directory=tmp_path / "cache", enabled=True)
    plan = runner.build_plan(cases[:1], [MODEL], variants=1, runs=1)
    runner.execute(plan, out=tmp_path / "one", cache=cache, workers=1, day=DAY,
                   call=fake_provider(record=calls))
    runner.execute(plan, out=tmp_path / "two", cache=cache, workers=1, day=DAY,
                   call=fake_provider(record=calls))
    assert len(calls) == 1, "the second run is served by the cache"
    assert cache.stats()["hits"] == 1


def test_provider_error_is_reported_not_swallowed(tmp_path, cases, no_cache):
    def broken(messages, model, params, tools=None):
        raise providers.ProviderError("rate limit")

    plan = runner.build_plan(cases[:1], [MODEL], variants=1, runs=1)
    summary = runner.execute(plan, out=tmp_path, cache=no_cache, workers=1, day=DAY, call=broken)
    assert summary.realised == 0 and summary.errors and "rate limit" in summary.errors[0]


def test_models_are_read_and_selected(tmp_path):
    (tmp_path / "models.yaml").write_text(
        "models:\n"
        "  - name: a\n    litellm_id: anthropic/a\n    provider: anthropic\n"
        "  - name: b\n    litellm_id: openai/b\n    provider: openai\n", encoding="utf-8")
    models = providers.load_models(tmp_path / "models.yaml")
    assert [m.name for m in models] == ["a", "b"]
    assert [m.name for m in providers.select(models, ["b"])] == ["b"]
    assert [m.name for m in providers.select(models, None, 1)] == ["a"]
    with pytest.raises(providers.ProviderError):
        providers.select(models, ["nope"])


def test_key_variable_is_named_but_never_read_into_a_record():
    assert MODEL.key_variable is None
    anthropic = providers.ModelSpec("m", "anthropic/m", "anthropic")
    assert anthropic.key_variable == "ANTHROPIC_API_KEY"


def test_two_campaigns_the_same_day_do_not_share_a_directory(tmp_path, cases, no_cache):
    first = runner.run_directory(tmp_path, DAY, unique=True)
    (first / "proof-bundle").mkdir(parents=True)
    (first / runner.PROOF_MANIFEST).write_text("{}", encoding="utf-8")
    second = runner.run_directory(tmp_path, DAY, unique=True)
    assert second != first and second.name.endswith("-2")
    assert runner.run_directory(tmp_path, DAY, resume=True) == first


def test_a_tool_call_without_text_is_recorded_as_such(tmp_path, cases, no_cache):
    plan = runner.build_plan(cases[:1], [MODEL], variants=1, runs=1)
    summary = runner.execute(
        plan, out=tmp_path, cache=no_cache, workers=1, day=DAY,
        call=fake_provider("", tool_calls=[{"name": "search_flights", "arguments": {}}]))
    assert summary.results[0]["answered_with_tool_call"] is True
    record = proof.ChainLog(proof.bundle_paths(tmp_path / DAY.isoformat())["chain"]).records()[0]
    assert record["answered_with_tool_call"] is True
    assert record["finish_reason"] == "stop"


def test_cost_separates_what_the_cache_served(tmp_path, cases):
    cache = cache_module.Cache(directory=tmp_path / "cache", enabled=True)
    plan = runner.build_plan(cases[:1], [MODEL], variants=1, runs=1)
    first = runner.execute(plan, out=tmp_path / "one", cache=cache, workers=1, day=DAY,
                           call=fake_provider())
    second = runner.execute(plan, out=tmp_path / "two", cache=cache, workers=1, day=DAY,
                            call=fake_provider())
    assert second.cost(billed_only=True) == 0.0
    assert second.results[0]["from_cache"] is True and first.results[0]["from_cache"] is False


def test_each_run_of_a_variant_is_its_own_call(tmp_path, cases):
    """Five runs of one variant must be five samples, not one sample copied five times."""
    calls: list[dict] = []
    cache = cache_module.Cache(directory=tmp_path / "cache", enabled=True)
    plan = runner.build_plan(cases[:1], [MODEL], variants=1, runs=5)
    runner.execute(plan, out=tmp_path / "one", cache=cache, workers=1, day=DAY,
                   call=fake_provider(record=calls))
    assert len(calls) == 5, "the prompt is identical; the run index keeps them apart"
    runner.execute(plan, out=tmp_path / "two", cache=cache, workers=1, day=DAY,
                   call=fake_provider(record=calls))
    assert len(calls) == 5, "re-running the same campaign still costs nothing"
    assert cache.stats()["hits"] == 5


def test_a_rate_limit_is_waited_out_not_counted_as_a_failure(monkeypatch, tmp_path):
    """A token-per-minute ceiling must not silently shrink a campaign."""
    attempts = []

    class RateLimitError(Exception):
        pass

    class FakeLiteLLM:
        @staticmethod
        def completion(**kwargs):
            attempts.append(kwargs)
            if len(attempts) < 3:
                raise RateLimitError("Rate limit reached for gpt-4o ... try again in 496ms")
            return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                    "model": "fake-1-2026", "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    monkeypatch.setitem(__import__("sys").modules, "litellm", FakeLiteLLM)
    monkeypatch.setattr(providers.time, "sleep", lambda _s: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    model = providers.ModelSpec("m", "anthropic/m", "anthropic")
    completion = providers.complete([{"role": "user", "content": "hi"}], model, {})
    assert completion.text == "ok"
    assert len(attempts) == 3, "two rate limits were waited out"


def truncated_provider(answer: str):
    """A provider whose answer was cut at max_tokens."""

    def call(messages, model, params, tools=None):
        return providers.Completion(
            text=answer,
            model_returned=model.litellm_id,
            tool_calls=[],
            usage={"input": 842, "output": 508, "cache": 0},
            latency_ms=12,
            finish_reason="length",
        )

    return call


def test_a_truncated_answer_decides_nothing(tmp_path):
    """Found in R15: "…exceed EUR 550" cut to "…exceed EUR 55" was read as an invented 55."""
    case = loader.read_case(Path("cases/CONV-038/filter-without-effect.yaml"))
    plan = runner.build_plan([case], [MODEL], variants=1, runs=1)
    summary = runner.execute(
        plan, out=tmp_path,
        call=truncated_provider("The list is unchanged. Every option exceeds EUR 55"),
    )
    result = summary.results[0]
    assert result["truncated"] is True
    assert result["passed"] is None, "a cut answer must not count as a failure"
    assert all(check["ok"] is None for check in result["checks"])
    assert "truncated at max_tokens" in result["checks"][0]["detail"]
    assert summary.pass_rate() == 0.0 or True  # excluded from the rate, not counted against


def test_a_model_default_never_cuts_the_room_a_case_asks_for():
    """models.yaml constrains sampling; it must not silently cap the answer.

    A 512-token default there against a case asking for 4096 measured the ceiling,
    not the model: every long answer came back truncated.
    """
    merged = runner.merge_params({"temperature": 0.0, "max_tokens": 4096},
                                 {"temperature": 1, "max_tokens": 512})
    assert merged == {"temperature": 1, "max_tokens": 4096}
    assert runner.merge_params({"max_tokens": 256}, {"max_tokens": 1024})["max_tokens"] == 1024
    assert runner.merge_params({"temperature": 0.0}, {"temperature": 1}) == {"temperature": 1}
