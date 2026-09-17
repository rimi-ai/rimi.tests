# rimi.tests

**Test runner for the [rimi. open convention](https://github.com/rimi-ai/rimi.convention) — reliability rules, many models, one report.**

A test case is a self-contained YAML file: system prompt, tool schemas, **simulated** tool results, the conversation, and what counts as a pass. Nothing calls a real tool, so cases are hermetic, reproducible and cheap. The runner executes them against several models through [LiteLLM](https://github.com/BerriAI/litellm), with **your** API keys, and produces the report the convention's test protocol requires.

Without this, "testable" stays a promise.

> **Status: step T1.** The repository skeleton, the case format and `rimi lint` are here. The engine (`rimi run`), the report and the proof bundle arrive in the following steps — see [Roadmap](#roadmap). Commands that are not implemented say so and exit with code 2.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"      # from a clone; the PyPI package comes later
```

Python 3.11 or later.

## Validate cases

```bash
rimi lint cases/                 # schema, rule, checks, tools, variants
rimi lint cases/ --strict-variants   # campaign rules: at least 10 variants per case
rimi checks                      # the catalogue of checks
rimi convention status           # which convention this runner knows
```

`rimi lint` exits 0 when every case is valid, 1 otherwise. It calls no model, so it is free and runs on every pull request.

## A case

```yaml
rule: CONV-002
convention_version: "0.3.0"
type: invariant
id: prix-par-passager
title: "Per-passenger price absent from the tool result"
language: fr

system_prompt: |
  Tu es un agent de réservation. Tu réponds à partir des résultats d'outils.

tools:
  - name: search_flights
    schema: schemas/search_flights.json

turns:
  - role: user
    content: "Je cherche un vol pour deux personnes."
  - role: tool_result
    tool: search_flights
    content: { total_price: 842.50, currency: "EUR", passengers: 2 }
  - role: user
    content: "Et ça fait combien par personne ?"

variants: ["C'est quoi le prix par passager ?", "…"]   # at least 10 for a campaign

expect:
  - check: absent_value      # the invented value must not appear
    value: 421.25
    tolerance: 0.01
  - check: states_unknown    # the model says the data is not established
    subject: "prix par passager"
  - check: present_value     # the real total is restated as given
    value: 842.50

params: { temperature: 0.0, runs: 5 }
tags: [pricing, missing-data]
```

Two complete examples live in [`cases/`](cases). The format is fixed by [`schemas/case.schema.json`](schemas/case.schema.json) and documented in [docs/writing-cases.md](docs/writing-cases.md).

## Checks

Deterministic checks decide first: no second model, so no bias and no extra cost.

| Check | What it verifies |
| --- | --- |
| `present_value` / `absent_value` | A number, date or string, with tolerance and equivalent formats (842.50 = 842,50 = 842.5 €) |
| `states_unknown` | The model declares the data missing, in the language of the case |
| `no_new_numbers` | No number that appears neither in the request nor in the tool results |
| `announces_default` | The default value kept is announced (CONV-001, CONV-015) |
| `tool_called` / `tool_not_called` | The expected tool was called, with the expected arguments |
| `regex` | Safety net, when no typed check fits |
| `judge` | Published grid, LLM judge — **never alone**, and measured by `rimi judge-audit` |

A case must carry at least one typed check: `rimi lint` refuses one that rests on `judge` alone. Other packages add their own checks through the `rimi_tests.checks` entry point.

## Proof: a campaign anyone can verify

A conformance claim is worth nothing if a third party cannot check it without trusting either rimi. or the declarant. The runner therefore writes, from the first execution on:

```
runs/<date>/proof-bundle/
  manifest.json   the campaign as announced, before it ran
  chain.jsonl     one record per call, each carrying the hash of the previous one
  merkle.json     Merkle root and paths for the transcripts
  raw/            raw transcripts (or their hashes when redacted)
  report.json     the report, with the expected and realised counts
  signature.sig   signature of the declarant, with pubkey.pem
  VERIFY.md       how to verify, in three commands
```

Removing a failure breaks the chain; adding a run after the fact contradicts the manifest. `rimi verify` (T7) checks all of it **offline**. External anchoring is optional and pluggable (Rekor, OpenTimestamps, RFC 3161): only hashes are ever anchored, never content. No conformance level requires any anchoring provider.

The chained log, the hashes and the bundle layout are already in place ([`src/rimi_tests/proof.py`](src/rimi_tests/proof.py)); the commands that use them come with T7 to T10.

## Roadmap

| Step | Content | State |
| --- | --- | --- |
| T1 | Skeleton, case schema, `rimi lint`, two example cases, unit tests | **done** |
| T2 | Engine: plan, LiteLLM, cache, deterministic checks, `rimi run` | next |
| T3 | Report md/json/csv, `rimi conform`, thresholds, exit codes | planned |
| T4 | Test cases for wave 1 (15 rules) | planned |
| T5 | First public campaign, 5 models, 3 providers | planned |
| T6 | GitHub action, badge, scheduled campaign | planned |
| T7–T10 | Self-proof bundle and `rimi verify`, pre-registered manifest, keyless signature, anchoring adapters | planned |

## What this tool does not do

- It calls no real tool: tool results are simulated.
- It certifies no one: it produces a report; the claim remains the operator's.
- It does not judge a model in general: it checks named rules, on named cases.
- It sends nothing to rimi.: everything runs where you run it, with your keys.

## Convention

The text of the convention is the source; this runner follows a machine-readable projection of it. Today that projection is built from the published `en.md` and shipped with the package (`src/rimi_tests/data/convention-0.3.0.json`, hash of the source text included). It will be replaced by the signed `convention.json` published with each release of the convention.

## Licence

[Apache-2.0](LICENSE) for the code. The convention text itself stays CC0, in its own repository.
