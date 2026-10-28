# prompt-eval-harness

A deterministic, offline-first prompt and agent evaluation regression
harness: a Python library, a CLI, and a GitHub Action that fail CI the
way a broken unit test does when a prompt, model, or retrieval change
silently degrades output.

> **Honest status (v0.1.0): this is an early-stage tool.** It was built
> as a first version, it has no users yet, and it does **not yet
> qualify for any six-month maintainer programme** (such as OpenAI
> Codex for Open Source or Anthropic Claude for Open Source, which
> reward already widely-used open-source projects). No stars,
> downloads, users, contributors, or benchmark results are claimed
> anywhere in this repository, because none exist yet. Adoption,
> if it comes, has to be earned by other developers actually using it.

## 5-minute quickstart

```bash
# Use a virtual environment (required on externally-managed systems
# such as Debian/Ubuntu, where system pip refuses package installs):
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
# then use .venv/bin/python -m prompt_eval ... (or activate the venv)
```
# Offline demo — no API key, no network, all 30 golden cases pass:
python -m prompt_eval run --cases examples/cases.yaml --provider stub

# The same run, with reports:
python -m prompt_eval run --cases examples/cases.yaml --provider stub \
  --markdown report.md --junit report.xml

# Watch the CI gate fail on purpose (1/3 passed, exit code 1):
python -m prompt_eval run --cases examples/failing.yaml --provider stub; echo "exit=$?"
```

Use it as a library, too:

```python
from prompt_eval import Case, Expectation, run_cases
from prompt_eval.providers import StubProvider

cases = [Case(id="greeting", prompt="Say hello",
              expected=[Expectation(type="exact", params={"value": "Hello!"})])]
report = run_cases(cases, StubProvider({"greeting": "Hello!"}))
print(report.passed_count, "/", report.total, "gate:", report.gate_passed)
```

## Case file format

A YAML file with a `cases` list. Each case has `prompt`, optional
`inputs` (substituted into `{placeholders}` in the prompt), an
`expected` list, and — for offline demos only — an optional
`stub_output`:

```yaml
version: 1
cases:
  - id: json-person
    prompt: "Return {name} as JSON"
    inputs: {name: Ada}
    expected:
      - type: json_schema
        schema:
          type: object
          required: [name, age]
          properties:
            name: {type: string}
            age: {type: integer, minimum: 0}
```

## Scorer catalogue

All scorers are deterministic and offline. None of them calls a model.

| Scorer | What it checks | Key parameters |
| ------ | -------------- | -------------- |
| `exact` | Output equals a value | `value`, `case_sensitive` (default true), `strip` (default true) |
| `regex` | Output matches a pattern | `pattern`, `ignore_case`, `multiline` |
| `json_schema` | Output parses as JSON and matches a schema **subset** | `schema` |
| `length` | Character / word bounds | `min_length`, `max_length`, `min_words`, `max_words` |
| `format` | Output is well-formed | `kind`: `json`, `email`, `url`, `lowercase`, `uppercase` |
| `contains_all` | Output contains every listed string | `strings`, `case_sensitive` (default true) |
| `citation` | RAG-style output cites sources | `min_citations` (default 1), `pattern`, `required_sources` |

**JSON Schema subset (read this before relying on it):** only
`type`, `enum`, `required`, `properties`, `additionalProperties`
(`false` only), `items`, `minItems`, `maxItems`, `minimum`,
`maximum`, `minLength`, `maxLength`, and `pattern` are checked.
Other keywords in a schema are ignored. This is **not** a full JSON
Schema validator, and the code does not claim otherwise.

**Citation default:** a citation is `[1]`, `[2]`, … or
`[source: name]`. Pass `pattern` to use a different marker style.

**LLM-as-judge:** deliberately not included in v1. If it is added
later, it will be advisory-only and must never be the default CI
gate — a non-deterministic judge cannot be a reproducible gate.

## Providers

- `stub` — returns each case's `stub_output`, or a placeholder
  response. Offline, free, and the right choice for demos, tests,
  and CI smoke runs. It proves the harness works; it does **not**
  prove a model is good.
- `openai` — any OpenAI-compatible `/chat/completions` endpoint.
  Configure with flags, never with a key in a file:

```bash
export OPENAI_API_KEY="..."   # from your provider, never commit it
python -m prompt_eval run --cases my-cases.yaml --provider openai \
  --model gpt-4o-mini --prompt-version v3
# A different endpoint / key variable:
python -m prompt_eval run --cases my-cases.yaml --provider openai \
  --base-url https://my-host.example/v1 --api-key-env MY_API_KEY_ENV
```

Keys are read from the environment at run time and are never logged.
If the key variable is unset, the run fails with a clear error
instead of silently passing or failing cases.

## Reports and the CI gate

- `--markdown report.md` — summary table, gate result, run metadata
  (provider/model, prompt version, harness version), and a section
  per failed case.
- `--junit report.xml` — JUnit XML, so CI systems and GitHub code
  scanning tooling can display failures per case.
- Exit code `0` means the gate passed (pass rate >= `--threshold`,
  default `1.0`, i.e. every case must pass). Exit code `1` means a
  case failed, the threshold was breached, or the provider failed.
  Exit code `2` means a usage/config error (bad file, duplicate
  case id, threshold out of range).
- `--threshold 0.9` allows a 90% pass rate; use it consciously, and
  prefer `1.0` for a regression gate — a threshold below 1.0 lets
  regressions through by design.

## CI guide

Copy `.github/workflows/prompt-eval.yml` from the template below, or
use the bundled `action.yml` (see below). The essential shape is:

```yaml
name: prompt-eval
on: [push, pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install .
      - run: >-
          python -m prompt_eval run
          --cases examples/cases.yaml --provider stub
          --markdown report.md --junit report.xml
      - uses: actions/upload-artifact@v4
        if: always()
        with: {name: prompt-eval-reports, path: "report.*"}
```

The bundled `action.yml` is a composite action wrapping the same
steps, so a consumer repo can call it with `cases`, `provider`,
`threshold`, and report-path inputs (see `action.yml`).

## What v1 deliberately leaves out

- Hosted dashboard, SaaS, accounts, or any server component.
- LLM-as-judge as a gating scorer (advisory-only if added later).
- Adapters for every LLM framework (LangChain, LangGraph,
  LlamaIndex, …), every language, or a visual prompt editor.
- Training, fine-tuning, dataset generation, or a prompt
  marketplace.
- A TypeScript port (a separate package later, not a v1 stretch
  goal).
- Full JSON Schema validation (subset only, documented above).

See [CHANGELOG.md](CHANGELOG.md) for the v0.1.0 scope and
[CONTRIBUTING.md](CONTRIBUTING.md) for how to add a scorer.
