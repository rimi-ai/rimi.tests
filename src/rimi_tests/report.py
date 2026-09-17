"""Report: report.md, report.json, summary.csv. Arrives with step T3.

Same content, three shapes. The report carries what the convention requires: version
and hash of the convention, providers, models and versions, parameters, pass rate per
rule and per model, and the failures themselves — not only the rates.

It also carries the expected count of executions (variants x runs x models) and the
realised count: a gap must be explained, otherwise the report is invalid (§13.2).
"""

from __future__ import annotations

# Thresholds of the test protocol; the convention projection carries the authoritative values.
MUST_THRESHOLD = 0.95
SHOULD_THRESHOLD = 0.80


def build(*_args, **_kwargs):
    raise NotImplementedError("the report arrives with step T3")


def write(*_args, **_kwargs):
    raise NotImplementedError("the report arrives with step T3")
