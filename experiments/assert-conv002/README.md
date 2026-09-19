# A judged check and a deterministic check, on the same answers

One rule, CONV-002. Two instruments score the same set of answers: an LLM judge — [ASSERT](https://github.com/responsibleai/ASSERT), used as its authors document it — and the deterministic check this repository already runs. Where they disagree, every answer is read and settled, and published in full.

The question is not which tool is better. It is what a judge's error rate actually is on a rule where a deterministic verdict exists, because the choice to use no judge has so far rested on an assumed figure rather than a measured one.

| File | What it holds |
| --- | --- |
| [PREREGISTRATION.md](PREREGISTRATION.md) | The protocol, committed before the first call was made. Not edited afterwards. |
| [RESULTS.md](RESULTS.md) | The four rates with exact intervals, what the reading settled, the deviations and the cost. |
| [disagreements.json](disagreements.json) | Every answer the two instruments scored differently, in full, with both verdicts and the reading. |

The pre-registration is in the commit before the results; the order is visible in the history and is the point of the exercise.

Limits are stated in both files: one rule, one judge model, two answering models, and a reference verdict that is a reading rather than an oracle. Nothing here transfers to another rule or another judge without being run there.
