"""LLM judge, used only where no typed check fits. Arrives with step T3.

The judge applies a published grid, and is itself measured: `rimi judge-audit` replays
a sample read by a human and publishes the agreement rate. Below 90%, a `judge` check
cannot carry a rule to Accepted status (specification §4).
"""

from __future__ import annotations

MIN_AGREEMENT = 0.90


def judge(*_args, **_kwargs):
    raise NotImplementedError("the judge arrives with step T3")


def audit(*_args, **_kwargs):
    raise NotImplementedError("judge audit arrives with step T3")
