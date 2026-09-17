# Checks

Deterministic checks decide first. They cost nothing, they do not drift, and their verdict can be recomputed by anyone from the raw transcript.

| Check | Parameters | What it verifies |
| --- | --- | --- |
| `present_value` | `value`, `[tolerance]`, `[unit]` | The value appears, in any equivalent format: `842.50`, `842,50`, `842.5 EUR`. |
| `absent_value` | `value`, `[tolerance]`, `[unit]` | A value no tool produced does not appear — the invented number. |
| `states_unknown` | `subject` | The model says the data is missing or not established, in the language of the case. |
| `no_new_numbers` | `[allow]` | No number that appears neither in the request nor in the tool results. |
| `announces_default` | `option`, `[mention]` | The default kept is named, not merely applied (CONV-001, CONV-015). |
| `tool_called` | `tool`, `[args]` | The expected tool was called, with the expected arguments. |
| `tool_not_called` | `tool` | No call the case forbids at this point (an irreversible action, for instance). |
| `regex` | `pattern`, `[mode]`, `[ignore_case]` | Safety net. `mode: absent` catches what must not be said. |
| `judge` | `rubric`, `[criteria]` | Published grid applied by an LLM judge. |

## Why `judge` is kept on a leash

A judge is another model, with its own drifts. The convention asks for verifiable results, so:

- a case must carry at least one typed check — `rimi lint` refuses one that rests on `judge` alone;
- the judge is measured: `rimi judge-audit` replays a sample read by a human and publishes the agreement rate;
- below 90% agreement, a `judge` check cannot carry a rule to Accepted status.

## Adding a check

Inside this repository, add a `CheckSpec` to `src/rimi_tests/checks.py`. Outside, declare one in the `rimi_tests.checks` entry point group:

```toml
[project.entry-points."rimi_tests.checks"]
my_check = "my_package.checks:MY_CHECK"
```

A check must: decide without a model when that is possible, explain its verdict in one line, and be recomputable from the transcript alone.
