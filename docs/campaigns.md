# Campaigns

A campaign is what the convention's test protocol asks for: enough models, enough providers, enough variants and runs — announced before it starts, and verifiable afterwards.

| Profile | Models | Providers | Variants | Runs | Use |
| --- | --- | --- | --- | --- | --- |
| `dev` | 1 | 1 | 3 | 1 | Writing cases. A few cents. Never declarable. |
| `campaign` | ≥ 5 | ≥ 3 | ≥ 10 | ≥ 5 | Public campaign, conforming to the protocol. |

Thresholds: a MUST or MUST NOT obligation passes at 95% of runs, a SHOULD at 80%. A rule reaches Stable status after two campaigns separated in time, on at least 3 providers and 5 models.

**How many runs.** A verdict is given per obligation with an exact interval, and 50 runs cannot establish 95%: even a perfect 50/50 comes out *inconclusive*. It takes **59** one-sided. Trials are variants × runs, so ten variants at six runs (`--runs 6`) settle it; a campaign warns when its trials cannot. A case carrying a `remedy` clause runs twice — without it, then with it — and the report shows both columns.

## Running one (from step T2)

```bash
cp models.example.yaml models.yaml     # your models; keys stay in the environment
export ANTHROPIC_API_KEY=…  OPENAI_API_KEY=…

rimi estimate --profile campaign       # cost and number of calls, before paying
rimi run --profile campaign --out runs/
rimi report runs/2026-09-20/
```

Costs are yours: nothing is hosted by rimi. The cache means that re-reading a report never pays for the calls twice.

## What a campaign leaves behind

```
runs/<date>/
  raw/                     every transcript, as received
  proof-bundle/            manifest, chained log, Merkle root, report, signature
```

- **Pre-registration.** The manifest is published before the run: cases and their hashes, models and versions, parameters, counts, thresholds, version of the convention. A campaign published without an earlier manifest is not admissible — that is what stops anyone from running ten campaigns and keeping the best one.
- **Chained log.** Each call is recorded with the hash of the previous record. Removing a failure breaks the chain.
- **Counts.** The report carries the expected count (variants × runs × models) and the realised one. A gap must be explained.
- **Failures are published**, not only rates. That is what makes a report contestable, and useful to providers.

`rimi verify` (T7) checks all of this offline. An external witness of time (Rekor, OpenTimestamps, RFC 3161) is optional: without one, the report simply says "date not attested".
