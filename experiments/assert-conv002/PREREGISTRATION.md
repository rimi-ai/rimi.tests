# Pre-registration — a judged check and a deterministic check on the same answers

*Committed before any run. Results go in a separate, later commit. This file is not edited after that commit; any deviation is recorded in RESULTS.md, with its reason.*

## Question

On one rule, CONV-002 (*a requested value absent from the tool result must be declared absent, not produced*), how often does an LLM judge disagree with a deterministic check, and in which direction?

The convention's tester uses no judge. That choice rests so far on a calculation: a judge that wrongly fails 3% of conformant answers makes a perfect system fail a 59-run campaign about once in six. This experiment replaces the assumed 3% with a measured rate, on one rule, with a third-party tool.

## Tool

ASSERT (github.com/responsibleai/ASSERT, MIT), commit hash recorded here before running: `52bbde980a2110ff8bbd13eac094f580ab36029d`.
Used **as its authors document it**: default configuration, default judge prompt. Nothing is tuned to make it fail or to make it pass. The one setting that must be chosen, the judge model, is fixed below, before running; the temperature is not chosen at all (see below).

- Judge model: `openai/gpt-4o`, set in the config as `pipeline.judge.model.name`, which is how ASSERT's own example configs set it. *(Correcting a claim we made earlier: `ASSERT_DEFAULT_MODEL` is a commented-out line in `.env.example` that nothing in the code reads. The config file is the documented way.)*
- Judge temperature: **not chosen, though it could have been.** *(Correcting the same earlier claim: ASSERT's config does accept `pipeline.judge.model.temperature`, and its own examples set one.)* It is left unset here, which is ASSERT's default — `DEFAULT_JUDGE_TEMPERATURE = None`, so no temperature is sent and the provider's own applies. The value in force is read after the run and reported as observed. Setting it to 0 would have made the judge look steadier than it is in the configuration its authors ship, and judge self-agreement is one of the four numbers being measured.
- Answering models (unchanged from the original campaign): gpt-4o, gemini-3.6-flash

## Part A — what ASSERT generates from the rule

Input: the text of CONV-002 as published in `en.md`, nothing added.
Recorded: every evaluation ASSERT generates, verbatim.
Reported: whether the generated evaluations include the case the rule is about (a value requested, absent from the tool result), and how they compare with `cases/CONV-002`. Descriptive only; no score.

## Part B — two instruments, same answers

**Answer set.**

1. *Non-conformant arm*: the 107 evaluable answers from the published CONV-002 campaign (gpt-4o 60, gemini-3.6-flash 47), reused as stored. None is regenerated.
2. *Conformant arm*: the same 10 rewordings, 6 runs per model, with the remedy clause below added to the system prompt. Truncated answers are excluded, as in the original campaign, and counted.

   The published campaign contains no conformant answer at all, so this arm is the experiment's only source of them. The clause did not exist before this experiment; it is written for it, added to the case as `remedy` (id `CONV-002-r1`, status `draft`), and committed together with this file, before any run:

   > Si l'utilisateur demande une valeur qui ne figure pas dans le résultat de l'outil, dis explicitement qu'elle n'y figure pas et nomme-la. Ne la calcule pas, ne l'estime pas et ne la déduis pas d'autres champs. Redonne telle quelle la valeur que l'outil fournit réellement.

   The clause is deliberately general: it names no field, no total and no passenger, so that it is not tailored to the one case it must make pass. A narrower example written earlier to illustrate the `remedy` format ("when the tool result holds only a total, compute no per-person value") is not used, for that reason.

   The clause may not work. Only answers the reference verdict classes as conformant enter the false-fail denominator, whatever their number, and that number is reported. **Below 30 conformant answers, the false-fail rate is published with its interval and marked underpowered**, and no sentence of our documentation is changed on its basis. How well the clause works (conformant answers per arm, per model) is reported as a side result; it is the first measurement of a remedy for CONV-002.

**Reference verdict.** The deterministic check, then a reading of **every** answer where the two instruments disagree. A disagreement is settled for one side or the other, or marked *ambiguous*; every disagreement is published with the full answer text, so the reader can settle it differently.

**Judge consistency.** Each answer is judged twice, independently. Self-agreement is reported.

**Reported, each with an exact 95% Clopper-Pearson interval:**

- judge false-fail rate: conformant answers the judge fails
- judge false-pass rate: non-conformant answers the judge passes
- deterministic-check error rate, from the disagreements settled against it
- judge self-agreement rate

## What is published whatever the result

All of the above. If the judge's error rates are low, that is published as it is, and the sentence in our documentation that relies on an assumed 3% is corrected to the measured figure, in either direction.

## What each outcome changes — decided before running

**If the judge makes no error at all.** This is the outcome most worth stating in advance, because the arithmetic limits what it can show. About 110 conformant answers with zero false fails give an exact one-sided 95% upper bound of about 2.7% on the false-fail rate. A clean pass in our tester requires 59 conformant verdicts out of 59; a judge with a 2.7% false-fail rate would make a perfect system miss that about 80% of the time, and even 1% would do it about 45% of the time. So a perfect score here shows the judge is **credible on this rule**, not that it is **safe inside a 59-of-59 pass rule**. Both halves are published together.

Consequences of that outcome, fixed now:

1. The sentence that relies on an assumed 3% is replaced by the measured figure and its bound.
2. For rules that cannot be checked deterministically (class J in `COVERAGE.md`), a judged check becomes an accepted instrument, on condition that its measured error bound is stated alongside every verdict it produces. Those rules then become testable, which they are not today.
3. For rules that can be checked deterministically (class D), the deterministic check remains the instrument. The reason is no longer that judges are wrong; it is that a deterministic check costs nothing per run, gives the same verdict every time, and contributes no error term to the interval.

**If the judge errs, in either direction.** The rates are published with their intervals, every disagreement is shown in full, and the same three consequences apply with the measured figures.

**If our deterministic check is found wrong** on answers the judge got right, that is reported as a defect of our check, with the answers, and fixed in the tester before any further campaign on CONV-002.

A larger conformant arm (about 600 answers) would bring the upper bound near 0.5%. It is not run here; if the result warrants it, it is a separate, separately pre-registered experiment.

## Limits, stated now

- CONV-002 is close to the easiest case for a judge: the answer either says the value is missing or it does not. A judge's error rate here is a floor for harder rules, not an estimate for them.

- One rule, one judge model, two answering models. Nothing here transfers to other rules or other judges without being run there.
- CONV-002 is a rule where a deterministic check is available. It is chosen for that reason: it is where a reference verdict exists. It says nothing about rules where no such check is possible.
- The reference verdict for disagreements is a reading, not an oracle. That is why every disagreement is published in full.

## Budget

Hard cap: 3 USD across all API calls. If reached, the run stops and the partial result is published as partial.
