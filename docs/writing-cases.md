# Writing a test case

A case is one YAML file that tests **one rule** of the convention. It is self-contained: the model sees a system prompt, tool schemas, simulated tool results and a conversation. Nothing else, and no network.

## Where the file goes

```
cases/<RULE>/<case-id>.yaml      e.g. cases/CONV-002/prix-par-passager.yaml
```

`case-id` is lowercase with dashes, unique inside the rule directory.

## The fields

| Field | Required | What it is |
| --- | --- | --- |
| `rule` | yes | Rule tested, e.g. `CONV-002`. It must exist in the cited version of the convention. |
| `convention_version` | yes | Version the case is written against, e.g. `0.3.0`. |
| `type` | yes | `invariant`, `default_convention` or `informative`, as the convention declares it. |
| `id`, `title` | yes | Identifier and one line saying what is being tested. |
| `language` | yes | Language of the dialogue (`fr`, `en`, …). Checks such as `states_unknown` depend on it. |
| `system_prompt` | yes | The instructions the tested system gives its model. |
| `tools` | no | Tool schemas exposed to the model. Declarative only. |
| `turns` | yes | The conversation. `user`, `assistant`, and `tool_result` for a **simulated** result. |
| `variants` | recommended | Rewordings of the tested request. A campaign asks for at least 10. |
| `expect` | yes | The success criteria. At least one typed check. |
| `params` | no | `temperature`, `top_p`, `max_tokens`, `runs`. A campaign asks for at least 5 runs. |
| `tags` | no | Free labels, useful to select a subset. |

## The rules behind the rules

- **Simulated tool results.** A case never calls anything. Put in `tool_result` exactly what the real tool would have returned — including what it does *not* contain, which is often the point.
- **One rule per case.** If a case can fail for two different reasons, split it.
- **At least one typed check.** `judge` may sit next to typed checks, never alone: a case that only asks a model to grade another model proves little.
- **Variants are rewordings, not new situations.** They measure robustness to phrasing, not a different test.
- **Anonymise.** No real person, company, booking reference or price tied to someone.

## Checking your case

```bash
rimi lint cases/CONV-002/            # schema, rule, checks, tools
rimi lint cases/ --strict-variants   # what a campaign requires
```

`rimi lint` prints the hash of each case (`case_sha256`). That hash goes into the manifest of a campaign and into every result: a report always says which exact case produced it.
