# Repairing `states_unknown`, scored against labels frozen first

The [judge experiment](../assert-conv002/RESULTS.md) went looking for a judge's error rate and found ours instead: of 94 answers that satisfy CONV-002, our deterministic check failed 45. Its pre-registration says a check found wrong is fixed before any further campaign on that rule. This is that fix, and its measurement.

**No model was called.** Everything here re-scores answers already stored.

## The order, which is the method

1. `a98e66b` — **the labels**, one line per stored answer, read and frozen. Nothing in `src/` had changed yet, so they cannot have been fitted to a check that did not exist.
2. `R29b` — the check repaired, and scored against that file.

The 240 stored answers were labelled from their text: 117 distinct texts, each read. They partition cleanly — every answer either states a per-passenger amount or says that amount is not in the tool result. **None does both, none does neither.**

| | base | remedy |
| --- | --- | --- |
| conformant | 0 | 94 |
| non-conformant | 93 | 0 |
| no text | 14 | 5 |
| truncated | 13 | 21 |

## What was wrong, in two parts

**The phrase list was literal, and short.** `UNKNOWN_PHRASES` held exact substrings. *"ne fournit pas"* was not among them, and *"n'est pas **explicitement** indiqué"* did not match *"n'est pas indiqué"* because one adverb sat in the middle. **43 of the 45 failures were this.** The list is now a closed list of patterns: the verbs are enumerated, only the adverb is free. Nothing is inferred and no judge is involved.

**The subject had to be named in the case's own words.** *"Le tarif unitaire ne figure pas"* says exactly what the rule asks, in words the case did not anticipate. **2 of the 45 failures were this.** A case now declares its own synonyms, in `subject_synonyms`; the check still refuses a declaration about a different subject, and still guesses nothing.

Third, and not a `states_unknown` matter: **an answer with no text is no longer an answer.** Nineteen of the stored answers carry no text, sixteen of them a tool call standing where the reply should be. They were scored as failures. They now leave the denominator, as a truncation does, and are counted and published separately.

## Before and after, against the frozen labels

| | false fail | false pass |
| --- | --- | --- |
| **Before** | **45/94 = 47.9 %** [39.0 %, 56.8 %] | 0/93 = 0.0 % [0.0 %, 3.2 %] |
| **After** | **3/94 = 3.2 %** [0.9 %, 8.0 %] | 0/93 = 0.0 % [0.0 %, 3.2 %] |

Exact Clopper-Pearson at 95 %. **The false-pass rate did not move.** Widening what counts as a declaration of absence did not let a single non-conformant answer through — which is the risk a wider check runs, and the reason it is reported next to the other column rather than on its own.

## The three answers where the labels and the check still disagree

All three declare the absence and stop there:

> Le tarif unitaire ne figure pas dans le résultat de l'outil.

> Le montant par passager n'est pas spécifié dans les résultats de l'outil.

They fail on `present_value`, not on `states_unknown`: the case also asks that the real total be restated, and these answers do not restate it. **CONV-002 does not require that.** So the remaining gap is not a defect of the repaired check; it is the case asking for more than the rule it tests. Whether a case may bundle a second obligation with the one it names is a question for the convention, not a bug to patch here, and it is left open rather than quietly fixed.

## What the numbers become

**The base arm, recounted.** Answers that are not answers leave the denominator.

| model | calls | evaluable | conformant | no text | truncated |
| --- | --- | --- | --- | --- | --- |
| gpt-4o | 60 | 54 | 0 | 6 | 0 |
| gemini-3.6-flash | 60 | 39 | 0 | 8 | 13 |

**0 of 54 and 0 of 39 — 93 answers, not 107.** The finding itself is unchanged: not one answer said the value was missing. What changes is the count it rests on, and the count was wrong in our favour, since it made the sample look larger than it was.

**The remedy arm, with the repaired check.** gpt-4o 57 of 60, gemini-3.6-flash 34 of 34 — 91 of 94 evaluable answers, the other three being the `present_value` cases above. This is the first measurement of a remedy for CONV-002 and it is not a campaign verdict: one case, two models, one provider each.

## One consequence worth stating

The case's fingerprint changed when `subject_synonyms` was added, so the identity recorded in earlier runs no longer matches the case as it now stands. That is the intended behaviour — a case that changed is a different case — and it means the campaign that produced these answers cannot be replayed against this file and called the same run. The answers are kept, their labels are kept, and both are published here.
