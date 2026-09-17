# Contributing to rimi.tests

Thank you. Two things matter here: a case must be verifiable by someone else, and a result must be reproducible from the raw transcripts.

## Before you start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
rimi lint cases/      # must pass
pytest                # must pass; no test ever calls a model
ruff check .
```

## Adding a test case

1. One file per case, under `cases/<RULE>/<case-id>.yaml`. Read [docs/writing-cases.md](docs/writing-cases.md).
2. Name the rule it tests, and the version of the convention you wrote it against.
3. At least one **typed** check. `judge` never stands alone.
4. At least 10 variants for a case meant for a campaign (`rimi lint --strict-variants`).
5. Tool results are **simulated**. A case never reaches the network.
6. Anonymise: no real customer, no real booking reference, no personal data.

A case is a claim about a rule. If a model fails it, the failure must be readable by anyone: keep the dialogue short and the expectation explicit.

## Adding a check

Typed checks live in `src/rimi_tests/checks.py`. Outside this repository, declare a `CheckSpec` in the `rimi_tests.checks` entry point group. A check must decide without a model whenever that is possible.

## Reporting a model failure

Open an issue with the case file, the model and version, the parameters, and the raw response. A failure that cannot be replayed is not a failure, it is an anecdote.

## Licence

By contributing you agree to release your contribution under [Apache-2.0](LICENSE).
