"""The verdict rule. These numbers are the reason the rule has three outcomes."""

from __future__ import annotations

import pytest

from rimi_tests import stats


def test_a_perfect_score_needs_59_runs_one_sided_and_72_two_sided():
    assert stats.required_trials() == 59
    assert stats.required_trials_two_sided() == 72
    assert stats.required_trials(0.80) == 14


def test_the_protocols_pass_mark_does_not_decide():
    """48/50 is what the protocol calls a pass. It establishes nothing."""
    assessment = stats.assess(48, 50)
    assert assessment.verdict is stats.Verdict.INCONCLUSIVE
    assert assessment.lower < 0.95 < assessment.upper
    assert assessment.more_runs > 0


@pytest.mark.parametrize("successes, trials, expected", [
    (50, 50, stats.Verdict.INCONCLUSIVE),   # not enough runs, however perfect
    (59, 59, stats.Verdict.PASS),           # exactly the one-sided requirement
    (72, 72, stats.Verdict.PASS),
    (40, 50, stats.Verdict.FAIL),
    (0, 20, stats.Verdict.FAIL),
    (19, 20, stats.Verdict.INCONCLUSIVE),
])
def test_three_outcomes(successes, trials, expected):
    assert stats.assess(successes, trials).verdict is expected


def test_bounds_are_the_clopper_pearson_ones():
    assert stats.lower_bound(59, 59) == pytest.approx(0.05 ** (1 / 59), rel=1e-9)
    assert stats.lower_bound(59, 59) >= 0.95
    assert stats.lower_bound(58, 58) < 0.95
    assert stats.upper_bound(50, 50) == 1.0
    assert stats.upper_bound(0, 20) == pytest.approx(1 - 0.05 ** (1 / 20), rel=1e-9)
    assert 0.98 < stats.upper_bound(48, 50) < 1.0


def test_a_should_recommendation_uses_the_lower_threshold():
    assert stats.threshold_for("SHOULD publish the measurement") == 0.80
    assert stats.threshold_for("MUST NOT invent a value") == 0.95
    assert stats.assess(45, 50, 0.80).verdict is stats.Verdict.PASS


def test_two_teams_disagree_about_half_the_time_at_the_bar():
    """The figures that make a bare comparison unusable."""
    assert stats.disagreement_probability(0.96) == pytest.approx(0.438, abs=0.002)
    assert stats.disagreement_probability(0.95) == pytest.approx(0.497, abs=0.002)


def test_impossible_scores_are_refused():
    for successes, trials in ((51, 50), (-1, 10), (1, -1)):
        with pytest.raises(ValueError):
            stats.assess(successes, trials)


def test_no_runs_is_inconclusive_not_a_pass():
    assessment = stats.assess(0, 0)
    assert assessment.verdict is stats.Verdict.INCONCLUSIVE
    assert assessment.more_runs == 59


def test_more_runs_is_what_would_settle_it():
    assessment = stats.assess(50, 50)
    assert assessment.more_runs == 9          # 59 in total
    assert "would settle it" in assessment.sentence()
