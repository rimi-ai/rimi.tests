"""Verdicts with a confidence interval, because a pass rate alone cannot decide.

The test protocol asks for 50 runs and a 95% threshold — 48 successes. Taken as a
plain comparison, that rule does not decide anything:

- a system truly at 96% gets opposite verdicts from two teams 43.8% of the time;
- a system truly at 95%: 49.7%;
- a *perfect* system judged with 3% false negatives fails 18.9% of the time; 5%: 45.9%;
- level A (40 obligations at once), perfect system, 2% judge error: passes 3.8% of the time.

So a verdict has three outcomes per obligation, never two: PASS when the lower bound
of the interval is above the threshold, FAIL when the upper bound is below it, and
INCONCLUSIVE otherwise — which asks for more runs instead of inventing a decision.

Intervals are Clopper-Pearson (exact, binomial), computed here without any dependency.

**One-sided, deliberately.** The question asked is "is the rate above the bar?", not
"where is the rate?". A perfect score therefore needs 59 runs to establish 95% at
alpha=0.05 one-sided — not 72, which is the two-sided figure for the same alpha:

    one-sided: n >= ln(alpha) / ln(threshold) = ln(0.05) / ln(0.95) = 58.4 -> 59
    two-sided: n >= ln(alpha/2) / ln(threshold) = ln(0.025) / ln(0.95) = 71.9 -> 72

`required_trials()` returns both, and the report says which one it used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

DEFAULT_ALPHA = 0.05
MUST_THRESHOLD = 0.95
SHOULD_THRESHOLD = 0.80


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


def _binomial_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ B(n, p). Exact terms, summed from the smaller tail."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    total = 0.0
    for i in range(k, n + 1):
        total += math.exp(
            math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * math.log(p) + (n - i) * math.log1p(-p)
        )
    return min(1.0, total)


def _bisect(target, lo: float = 0.0, hi: float = 1.0, tolerance: float = 1e-12) -> float:
    """Root of an increasing function on [lo, hi]."""
    for _ in range(200):
        mid = (lo + hi) / 2
        if hi - lo < tolerance:
            return mid
        if target(mid) > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def lower_bound(successes: int, trials: int, alpha: float = DEFAULT_ALPHA) -> float:
    """Clopper-Pearson lower bound: the smallest p for which the score is not surprising."""
    _check(successes, trials)
    if successes == 0:
        return 0.0
    if successes == trials:
        return alpha ** (1.0 / trials)
    return _bisect(lambda p: _binomial_sf(successes, trials, p) - alpha)


def upper_bound(successes: int, trials: int, alpha: float = DEFAULT_ALPHA) -> float:
    """Clopper-Pearson upper bound, one-sided at the same level."""
    _check(successes, trials)
    if successes == trials:
        return 1.0
    if successes == 0:
        return 1.0 - alpha ** (1.0 / trials)
    # P(X <= successes | p) falls as p rises; the root is where it equals alpha.
    return _bisect(lambda p: alpha - (1.0 - _binomial_sf(successes + 1, trials, p)))


def _check(successes: int, trials: int) -> None:
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError(f"impossible score: {successes}/{trials}")


@dataclass(frozen=True)
class Assessment:
    """What a set of runs establishes about one obligation."""

    successes: int
    trials: int
    threshold: float
    alpha: float
    verdict: Verdict
    lower: float
    upper: float
    more_runs: int = 0

    @property
    def rate(self) -> float:
        return self.successes / self.trials if self.trials else 0.0

    def as_dict(self) -> dict:
        return {
            "successes": self.successes,
            "trials": self.trials,
            "rate": round(self.rate, 4),
            "threshold": self.threshold,
            "alpha": self.alpha,
            "verdict": self.verdict.value,
            "interval": [round(self.lower, 4), round(self.upper, 4)],
            "more_runs_for_a_perfect_score": self.more_runs,
        }

    def sentence(self) -> str:
        """One line a report can print as is."""
        interval = f"[{self.lower:.3f}, {self.upper:.3f}]"
        if self.verdict is Verdict.PASS:
            return (f"{self.successes}/{self.trials} — above {self.threshold:.0%} "
                    f"(lower bound {self.lower:.3f})")
        if self.verdict is Verdict.FAIL:
            return (f"{self.successes}/{self.trials} — below {self.threshold:.0%} "
                    f"(upper bound {self.upper:.3f})")
        return (f"{self.successes}/{self.trials} — {interval} straddles {self.threshold:.0%}; "
                f"{self.more_runs} more perfect run(s) would settle it")


def assess(successes: int, trials: int, threshold: float = MUST_THRESHOLD,
           alpha: float = DEFAULT_ALPHA) -> Assessment:
    """Three outcomes, never two."""
    _check(successes, trials)
    if trials == 0:
        return Assessment(0, 0, threshold, alpha, Verdict.INCONCLUSIVE, 0.0, 1.0,
                          required_trials(threshold, alpha))
    low, high = lower_bound(successes, trials, alpha), upper_bound(successes, trials, alpha)
    if low >= threshold:
        verdict = Verdict.PASS
    elif high < threshold:
        verdict = Verdict.FAIL
    else:
        verdict = Verdict.INCONCLUSIVE
    more = 0
    if verdict is Verdict.INCONCLUSIVE:
        more = max(0, _trials_for_perfect_tail(successes, trials, threshold, alpha) - trials)
    return Assessment(successes, trials, threshold, alpha, verdict, low, high, more)


def _trials_for_perfect_tail(successes: int, trials: int, threshold: float, alpha: float,
                             limit: int = 5000) -> int:
    """How many trials in total would settle it, if every added run succeeded."""
    failures = trials - successes
    total = trials
    while total < limit:
        total += 1
        if lower_bound(total - failures, total, alpha) >= threshold:
            return total
    return limit


def required_trials(threshold: float = MUST_THRESHOLD, alpha: float = DEFAULT_ALPHA) -> int:
    """Runs needed for a perfect score to establish `threshold`, one-sided."""
    return math.ceil(math.log(alpha) / math.log(threshold))


def required_trials_two_sided(threshold: float = MUST_THRESHOLD, alpha: float = DEFAULT_ALPHA) -> int:
    """The same figure computed two-sided — documented for comparison, not used for verdicts."""
    return math.ceil(math.log(alpha / 2) / math.log(threshold))


def threshold_for(obligation: str) -> float:
    """MUST and MUST NOT at 95%, SHOULD at 80% — the thresholds of the test protocol."""
    return SHOULD_THRESHOLD if obligation.upper().startswith("SHOULD") else MUST_THRESHOLD


def disagreement_probability(true_rate: float, trials: int = 50, threshold: float = MUST_THRESHOLD,
                             alpha: float = DEFAULT_ALPHA) -> float:
    """Chance that two teams running the same campaign reach opposite verdicts.

    This is what makes the plain comparison unusable, and it is cheap to show.
    """
    passes = 0.0
    for successes in range(trials + 1):
        probability = math.exp(
            math.lgamma(trials + 1) - math.lgamma(successes + 1) - math.lgamma(trials - successes + 1)
            + successes * math.log(true_rate) + (trials - successes) * math.log1p(-true_rate)
        ) if 0 < true_rate < 1 else float(successes == trials * true_rate)
        if successes / trials >= threshold:
            passes += probability
    return 2 * passes * (1 - passes)
