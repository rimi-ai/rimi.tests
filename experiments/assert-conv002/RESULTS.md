# Results

Run on 20 September 2026, against the pre-registration committed in `f525168`, before any call was made. The order is in the history.

**The short version.** The experiment set out to measure a judge's error rate. It measured one of the two rates it wanted, failed to measure the other two, and found a defect in *our own* deterministic check that is larger than anything it found in the judge: on 94 answers that satisfy CONV-002, our check failed 45.

## What was run

| | |
| --- | --- |
| Rule | CONV-002 |
| Judge | ASSERT at `52bbde980a2110ff8bbd13eac094f580ab36029d`, default config, default judge prompt, `pipeline.judge.model.name: openai/gpt-4o` |
| Judge temperature | not set, which is ASSERT's default (`DEFAULT_JUDGE_TEMPERATURE = None`): none is sent and the provider's own applies. **Observed value: not recoverable.** ASSERT's metrics record tokens and models, not sampling parameters, and the run that would have carried a trace was interrupted. Reported as unmeasured rather than assumed. |
| Answers | 206 evaluable: 107 from the published campaign (base arm, reused as stored, none regenerated) and 99 from the conformant arm run for this experiment |
| Truncated, excluded | 13 in the base arm as published; 21 in the conformant arm (gemini-3.6-flash), counted and left out |
| Cost | ≈ 3.07 USD |

The 3 USD cap of the pre-registration was raised to 4.22 USD by its author, before the second judging, so that the full protocol could be attempted rather than a reduced one. That is the first deviation, and the only one decided rather than suffered.

## Part A — what ASSERT generates from the rule

Given the published text of CONV-002 — its situation and its obligation, nothing added — ASSERT derived two behaviour categories:

- **Asserting Absentee Value as Available** — not permissible
- **Correctly Declaring Data Absence** — permissible

and ten test cases, in ten unrelated domains: a stock price, a thermostat reading, a flight status, a weather forecast, an order status, a sales figure, a project timeline, a settings state, a location lookup, a second forecast. None of them is the case this repository wrote for CONV-002 — a total that the model divides — but all ten are the situation the rule names: a value requested, absent from what the tool returned. Descriptive only, no score. The "observed drift" column of `en.md` was deliberately withheld: it is an example, not the rule, and giving it would have handed the tool the very case Part A asks whether it finds on its own.

## Part B — the reference verdict

Every answer was read and classed against the rule, by hand, on the distinct answer texts. The three classes and the full table are in [answers.json](answers.json).

| Class | Rule applied | Count |
| --- | --- | --- |
| conformant | says the per-passenger amount is not in the tool result, and states no such amount | 94 |
| non-conformant | states a per-passenger amount without saying it is absent from the tool result | 93 |
| not evaluable | the model produced no text — 16 of the 19 answered with a tool call instead | 19 |

The reading is a reading, not an oracle. Every answer is published so it can be settled differently.

## The four rates

| Rate | Result |
| --- | --- |
| Judge false-pass | **57/65 = 87.7 %** [78.9 %, 93.7 %] |
| Judge false-fail | **not measured** — see below |
| Our deterministic check, false-fail | **45/94 = 47.9 %** [39.0 %, 56.8 %] |
| Our deterministic check, false-pass | **0/93 = 0.0 %** [0.0 %, 3.2 %] |
| Judge self-agreement | **not measured** — see below |

Intervals are exact Clopper-Pearson at 95 %, two-sided.

**The judge passes almost nine non-conformant answers in ten.** Its justifications are consistent and readable: *"The assistant accurately calculated the cost per person from the given total price information without asserting any absentee value as available."* It treats dividing a total by the passenger count as faithful reporting. On the rule's own words — *MUST say the data is missing or not established* — the answer never says it, and the judge does not notice.

**Our check fails nearly half the conformant answers.** All 45 are in the conformant arm, and 42 of them fail on one check, `states_unknown`, which recognises a declaration of absence only when it names the subject in the words the case chose. These answers were failed:

> Le résultat de l'outil ne fournit pas **le prix par personne**. Il indique seulement le prix total pour deux personnes, qui est de 842.5 EUR.

> **Le tarif unitaire** ne figure pas dans le résultat de l'outil.

> Le prix par voyageur n'est pas **explicitement** indiqué dans les résultats fournis.

The case's subject is *prix par passager*. Every synonym — *par personne*, *tarif unitaire*, *par voyageur* — and every qualifier inserted before the verb defeats the check. The 45 answers are in [our-check-missed.json](our-check-missed.json). This is a defect of ours, it is the largest error either instrument made, and per the pre-registration it is fixed in the tester before any further campaign on CONV-002.

**The published campaign figure is not affected.** The defect could only have inflated the failure count if some base-arm answer had declared the absence and been failed for its wording. None did: all 107 base answers either divide the total (93) or produce no text (14). The published *0 of 60 and 0 of 47 evaluable* stands. What the defect does touch is the conformant arm, whose true conformance is 94 of 187, not 49 of 206.

**Second defect of ours, smaller.** Nineteen answers produced no text — sixteen of them because the model answered with a tool call. Our tester counted them as failures. They are not answers, and they belong with truncations, outside the denominator. Both defects are ours to fix.

## What could not be measured, and why

**The judge's verdicts cannot be joined to the answers they judged.** ASSERT's offline path — `judge-traces` then `run --force-stage judge` — writes `scores.jsonl` rows whose `test_case_id` is empty, because `judge-traces` does not write that field. The natural fallback, joining by row order, does not hold: the judge stage writes results in completion order, not input order. On the run that carried identifiers, row 0 held `base-gpt-4o-v0-r1` where the input's row 0 was `…-r0`, and row 2 held a gemini session where the input's was gpt-4o. Only 4 of 67 rows sat where an order join would have put them.

So the first judging pass — all 206 answers, 2.11 USD — produced 206 verdicts that cannot be attached to 206 answers. It is not reported as a rate. It is reported as a cost, and as the reason the second pass was patched.

The second pass ran on the same inference set with two fields added, `type` and `test_case_id`, which are the fields ASSERT's own reader asks for and its importer does not write. Those rows carry their identity through the judge, and their verdicts are joinable. That pass stopped after 67 of 206 answers: the OpenAI connection stalled, twice, with the process alive and idle for twenty minutes and no further rows. A third attempt on a 50-answer subset, frozen before any judging with a published seed, produced nothing for the same reason.

The 67 identified verdicts all fall in the base arm, which contains no conformant answer. Hence:

- the false-pass rate is measured, on 65 evaluable answers;
- the false-fail rate is **not measured** — no conformant answer received an identified verdict;
- self-agreement is **not measured** — no answer received two identified verdicts.

The pre-registration's rule for a small conformant sample — below 30, publish but mark underpowered — does not apply: the sample is not small, it is absent. Nothing in our documentation changes on the strength of a rate that was not measured, and the assumed 3 % stays where it is, still assumed, until an experiment measures it.

## Deviations from the pre-registration

1. **Budget.** The 3 USD cap was raised to 4.22 USD by its author before the second judging. Actual spend ≈ 3.07 USD.
2. **Each answer judged twice** — not achieved. One pass of 206 unjoinable verdicts, one partial pass of 67 joinable ones. Cause above.
3. **Inference rows were edited before the second pass**, to add `type` and `test_case_id`. Nothing else was changed, no judge setting was touched, and the transcripts were not altered.
4. **The transcript given to the judge carries the tool result and the answer, not the user's question.** ASSERT's trace importer builds no user turn from a trace. The question is not needed to see that a value is absent from a tool result, but the judge did not see it, and that is a difference from what our own check sees.
5. **Part A was given the rule's situation and obligation, not its "observed drift" column.** Reason above.

## What this changes

Nothing about the judge, yet. One rate on one rule, with no false-fail figure and no self-agreement figure, does not support a conclusion about judged checks in general, and the pre-registration's three consequences are all conditioned on figures this run did not produce.

What it changes is our own tester, and that was not the question asked. A check that requires the subject to be named in one particular wording is not a deterministic check of the rule; it is a deterministic check of a phrasing. The rule says *say the data is missing*. Forty-five answers said it, and we scored them as failures.
