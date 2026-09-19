# Coverage — which rules have test cases, which can have them, and in what order

One line per rule of the convention: 35 in Part A, 11 in Part B, 20 in Part C. The principles are
listed separately and carry no testability letter — a principle is not tested, the rules derived from
it are.

**Testability**

| | |
| --- | --- |
| **D** | A deterministic verdict is possible: the result is settled by comparing strings or structure with data the case already holds, without interpretation. |
| **J** | A judge is needed: the verdict requires reading what the answer means. |
| **S** | Tested on the system — prompt, tool schemas, code, counters — not on a model's answer. |
| **N** | Not testable by campaign: the rule is addressed to the person making the request (see [issue #23](https://github.com/rimi-ai/rimi.convention/issues/23)). |

Where a rule could go either way, both letters are written, and the line says where the doubt sits.

## Totals

| Rules | 66 |
| --- | --- |
| D | 31 |
| D or J | 5 |
| J | 3 |
| S | 21 |
| N | 6 |
| With a test case | 3 |
| Without a test case | 63 |
| Real case: several | 5 |
| Real case: one incident | 23 |
| Real case: to be documented | 37 |

`cases/` also holds four cases for CONV-038, a rule proposed in
[issue #11](https://github.com/rimi-ai/rimi.convention/issues/11) and not yet part of the convention;
it is not counted above.

## Part A — the model in conversation

CONV-001 carries a full template, including test-case dialogues; the other thirty-four are Draft rows. The real-case column below reads the "Observed drift" column of `en.md`.

| Id | Type | Addressed to | Testability | Why | Test case | Real case |
| --- | --- | --- | --- | --- | --- | --- |
| CONV-001 | Convention | model | **D** | The named option and the words of the question are known strings: the check reads whether option 1 is announced and whether the same question comes back. | cases/CONV-001/oui-sur-alternative.yaml | n/a |
| CONV-002 | Invariant | model | **D** | The value is absent from the tool result by construction, so producing it is settled by looking for it in the answer. | cases/CONV-002/prix-par-passager.yaml | documented, several |
| CONV-003 | Invariant | model | **D** | The true values are in the fixture; a narrated value that differs is caught by comparison. | — | documented, several |
| CONV-004 | Invariant + default | model | **D or J** | Citing both values is a string check, but deciding that the answer flags the conflict rather than listing two numbers takes reading. | — | one incident |
| CONV-005 | Invariant | model | **D** | No tool ran, so any concrete result in the answer was produced from nothing. | — | documented, several |
| CONV-006 | Invariant | model | **D or J** | Returning the value unchanged is checkable; recognising that the answer inferred a meaning from the field name is not. | — | one incident |
| CONV-007 | Invariant | model | **D or J** | The allowance belongs to one carrier in the fixture; catching it attached to another needs the sentence read, not only the number found. | — | to be documented |
| CONV-008 | Invariant | model | **D** | The system date is given in the case; any other date in the answer fails. | — | one incident |
| CONV-009 | Convention | model | **D** | The answered item is known: the check is whether it is asked again. | — | to be documented |
| CONV-010 | Invariant | model | **D** | Exact restatement is character comparison. This is the simplest case in the convention. | — | one incident |
| CONV-011 | Invariant | model | **D or J** | The prohibited item is a known string and its absence is checkable; whether an allowed alternative was offered is a judgement. | — | to be documented |
| CONV-012 | Convention | model | **D** | The retrieval time sits in the tool result: present in the answer or absent. | — | to be documented |
| CONV-013 | Invariant | model | **D** | Hedges are a closed list of words, and the exact value is known. | — | to be documented |
| CONV-014 | Invariant | model | **D** | The filters are known strings; an absence claimed without naming them fails. | — | one incident |
| CONV-015 | Convention | model | **D** | The filled-in value is chosen by the case: the check is whether the answer names it. | — | to be documented |
| CONV-016 | Invariant | model | **D** | Origin is a declared field in the output; a regex decides. | cases/CONV-016/ — 5 cases | to be documented |
| CONV-017 | Invariant | model | **D** | Amount, deadline and conditions are in the fixture: each is present or not. | — | to be documented |
| CONV-018 | Convention | model | **D** | Give each question a distinct value; which value the answer carries says where the reply was attached. | — | to be documented |
| CONV-019 | Invariant | model | **D** | Nothing in the case can support an answer, so any result produced is a failure. | — | to be documented |
| CONV-020 | Informative | model | **D** | Saying it is an AI is phrase-level: presence decides. | — | to be documented |
| CONV-021 | Convention | model | **D** | Order is positional: the known answers appear in the order asked, or they do not. | — | to be documented |
| CONV-022 | Convention | model | **D** | Acting early shows as a result produced before the last fragment arrives. | — | to be documented |
| CONV-023 | Convention | model | **J** | Whether a question is about what blocks the action is a matter of meaning. | — | to be documented |
| CONV-024 | Invariant | model | **D** | Under pressure the answer either keeps the tool's value or adopts the user's: two known strings. | — | to be documented |
| CONV-025 | Invariant | model | **D** | The tool's value is known; the check is whether it is cited. | — | to be documented |
| CONV-026 | Invariant | model | **D** | "Confirmed" against a segment in an unconfirmed state is a word against a known state. | — | one incident |
| CONV-027 | Invariant | model | **D or J** | Common promise forms are a phrase list, but a promise can be worded in ways no list closes. | — | to be documented |
| CONV-028 | Informative | model | **D** | The injected instruction has one observable effect; its absence from the answer decides. | — | to be documented |
| CONV-029 | Convention | model | **D** | Zone, currency and unit are tokens: present or absent. | — | to be documented |
| CONV-030 | Invariant | model | **D** | Re-checking shows in the trace as a second tool call. | — | to be documented |
| CONV-031 | Invariant | model | **D** | Either the total matches the tool's or the steps are shown; both are checkable without reading. | — | to be documented |
| CONV-032 | Invariant | model | **D** | The handover sentence is present, and nothing follows it. | — | to be documented |
| CONV-033 | Convention | model | **D** | The updated constraints are known values; the restatement carries them or does not. | — | to be documented |
| CONV-034 | Informative | model | **D** | The sensitive string is in the fixture; the check is that it does not come back. | — | to be documented |
| CONV-035 | Invariant | model | **J** | Weighing clues against a source is the reasoning itself; no string settles it. | — | one incident |

## Part B — prompts and tool schemas

`en.md` states that these are checked by static audit, without running the LLM. That is why every line is S.

| Id | Type | Addressed to | Testability | Why | Test case | Real case |
| --- | --- | --- | --- | --- | --- | --- |
| CONC-001 | Invariant | system | **S** | Read the prompt: each conditional branch covers the opposite case or it does not. | — | one incident |
| CONC-002 | Invariant | system | **S** | Answered by the call log and the prompt text: a declared tool called or never called, a removed tool still cited or not. | — | documented, several |
| CONC-003 | Invariant | system | **S** | Compares a field name with the values it actually carries, in the schema and in the data. | — | one incident |
| CONC-004 | Convention | system | **S** | Compares field names with the trade's published nomenclature. | — | one incident |
| CONC-005 | Invariant | system | **S** | Duplicate detection over the prompt text. | — | one incident |
| CONC-006 | Convention | system | **S** | The markers are counted mechanically; what each one governs is read once by the auditor, not by a judge at run time. | — | one incident |
| CONC-007 | Invariant | system | **S** | Feed the check a wrong value with the field present: it either compares values or only existence. | — | documented, several |
| CONC-008 | Invariant | system | **S** | Send an unknown identifier and watch for a visible error instead of a silent default. | — | one incident |
| CONC-009 | Convention | system | **S** | The closed list is in the prompt or it is not. | — | to be documented |
| CONC-010 | Invariant | system | **S** | Compares the deployed prompt with its versioned copy. | — | one incident |
| CONC-011 | Convention | system | **S** | Each rule declares a scope or does not; the default reading is applied by the auditor. | — | to be documented |

## Part C — frugality

Part C rules carry no type in `en.md`; the column is left empty rather than invented.

| Id | Type | Addressed to | Testability | Why | Test case | Real case |
| --- | --- | --- | --- | --- | --- | --- |
| SOB-001 | — | system | **S** | Which model runs is a system setting; the verdict comes from campaign results, not from one answer. | — | to be documented |
| SOB-002 | — | system | **S** | Whether a deterministic path exists for a task is read in the code, not in an answer. | — | one incident |
| SOB-003 | — | system | **S** | The judge's call count under a layered guard is counted. | — | one incident |
| SOB-004 | — | model | **D** | A redundant call shows in the trace: same tool, same arguments, result already in context. | — | to be documented |
| SOB-005 | — | system | **S** | Prompt size, cached share and duplicates are measured on the prompt itself. | — | one incident |
| SOB-006 | — | model | **J** | "Length matching the question" has no threshold that is not arbitrary; deciding it is reading. | — | to be documented |
| SOB-007 | — | system | **S** | The cap is in the code: loops stop or they do not. | — | one incident |
| SOB-008 | — | system | **S** | A service's state is read from the infrastructure. | — | one incident |
| SOB-009 | — | system | **S** | The obligation is to publish the counters; the check is that the report exists and carries them. | — | to be documented |
| SOB-010 | — | model | **D** | The change is compared with the source: only the relevant part moved, or more. | — | one incident |
| SOB-011 | — | system | **S** | Read the tool schema: partial read and targeted change are offered or not. | — | one incident |
| SOB-012 | — | requester | **N** | Addressed to the person making the request; there is no campaign to run on a human (issue #23). | — | one incident |
| SOB-013 | — | requester | **N** | Addressed to the requester; same limit as SOB-012. | — | one incident |
| SOB-014 | — | requester | **N** | Addressed to the requester; same limit as SOB-012. | — | to be documented |
| SOB-015 | — | requester | **N** | Addressed to the requester; same limit as SOB-012. | — | to be documented |
| SOB-016 | — | requester | **N** | Addressed to the requester; same limit as SOB-012. | — | to be documented |
| SOB-017 | — | requester | **N** | Addressed to the requester; same limit as SOB-012. | — | to be documented |
| SOB-018 | — | model | **D** | The trace shows what was read: a targeted search, or everything. | — | to be documented |
| SOB-019 | — | system | **S** | The scheduler and its trigger are system objects. | — | to be documented |
| SOB-020 | — | system | **S** | Routing share, escalation rate and cost per successful task are counters on the system. | — | to be documented |

## Principles

P-01 to P-14 ground the rules and are not tested directly: a principle is verified through the rules
derived from it. `en.md` marks P-11 to P-14 as candidates — P-12 with no observation at all, P-11 with
three, P-14 with one. A principle whose rules have no test case is supported by nothing measured.

## Order of work

The 28 rules that can be settled deterministically and have no test case, in the order the
cases will be written: invariants first, then default conventions, then informative rules; within each
group, a rule with a real case before one whose case is still to be documented. No date is promised.

| # | Id | Type | Real case |
| --- | --- | --- | --- |
| 1 | CONV-003 | Invariant | documented, several |
| 2 | CONV-005 | Invariant | documented, several |
| 3 | CONV-008 | Invariant | one incident |
| 4 | CONV-010 | Invariant | one incident |
| 5 | CONV-014 | Invariant | one incident |
| 6 | CONV-026 | Invariant | one incident |
| 7 | CONV-013 | Invariant | to be documented |
| 8 | CONV-017 | Invariant | to be documented |
| 9 | CONV-019 | Invariant | to be documented |
| 10 | CONV-024 | Invariant | to be documented |
| 11 | CONV-025 | Invariant | to be documented |
| 12 | CONV-030 | Invariant | to be documented |
| 13 | CONV-031 | Invariant | to be documented |
| 14 | CONV-032 | Invariant | to be documented |
| 15 | CONV-009 | Convention | to be documented |
| 16 | CONV-012 | Convention | to be documented |
| 17 | CONV-015 | Convention | to be documented |
| 18 | CONV-018 | Convention | to be documented |
| 19 | CONV-021 | Convention | to be documented |
| 20 | CONV-022 | Convention | to be documented |
| 21 | CONV-029 | Convention | to be documented |
| 22 | CONV-033 | Convention | to be documented |
| 23 | CONV-020 | Informative | to be documented |
| 24 | CONV-028 | Informative | to be documented |
| 25 | CONV-034 | Informative | to be documented |
| 26 | SOB-010 | — | one incident |
| 27 | SOB-004 | — | to be documented |
| 28 | SOB-018 | — | to be documented |

The D-or-J rules are not in this list: each needs its doubt settled first, by trying a deterministic
check and seeing what it misses. The J and N rules are not in it either — a judge has to be measured
before it can be trusted, and a rule addressed to a human has no campaign.
