# prompt-eval-harness

[![CI](https://github.com/AsherLucas/prompt-eval-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/AsherLucas/prompt-eval-harness/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python >= 3.11](https://img.shields.io/badge/python-%3E%3D3.11-blue.svg)](pyproject.toml)

A deterministic, offline-first prompt and agent evaluation regression
harness: a Python library, a CLI, and a GitHub Action that fail CI the
way a broken unit test does when a prompt, model, or retrieval change
silently degrades output.

> **Honest status (v0.2.0): this is an early-stage tool.** It has
> no users yet, and it does **not yet qualify for any six-month
> maintainer programme** (such as OpenAI Codex for Open Source or
> Anthropic Claude for Open Source, which reward already
> widely-used open-source projects). No stars, downloads, users,
> contributors, or benchmark results are claimed anywhere in this
> repository, because none exist yet. Adoption, if it comes, has
> to be earned by other developers actually using it.

## 5-minute quickstart

```bash
# Use a virtual environment (required on externally-managed systems
# such as Debian/Ubuntu, where system pip refuses package installs):
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
# Commands below use .venv/bin/python so they work without activating
# the venv; after `source .venv/bin/activate`, plain `python` works too.

# Offline demo — no API key, no network, all 30 golden cases pass:
.venv/bin/python -m prompt_eval run --cases examples/cases.yaml --provider stub

# The same run, with reports:
.venv/bin/python -m prompt_eval run --cases examples/cases.yaml --provider stub \
  --markdown report.md --junit report.xml

# Watch the CI gate fail on purpose (1/3 passed, exit code 1):
.venv/bin/python -m prompt_eval run --cases examples/failing.yaml --provider stub; echo "exit=$?"

# Catch a prompt regression with run-diff (see
# examples/prompt-regression/README.md for the verified output):
.venv/bin/python -m prompt_eval run --cases examples/prompt-regression/cases.yaml \
  --provider stub --prompt-version v1 --json /tmp/baseline.json
.venv/bin/python -m prompt_eval run --cases examples/prompt-regression/regressed.yaml \
  --provider stub --prompt-version v2 --json /tmp/new.json
.venv/bin/python -m prompt_eval diff --baseline /tmp/baseline.json \
  --new /tmp/new.json; echo "diff exit=$?"
# (The same baseline is also checked in as
# examples/prompt-regression/baseline.json.)
```

Verified in a clean venv against this checkout: golden cases
`30/30 passed`, failing example `1/3 passed` with exit code 1,
prompt-regression example `6/6` baseline vs `5/6` regressed with
exactly one `Pass -> Fail` case (`refund-window`), diff exit 1.

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
| `json_schema` | Output parses as JSON and matches a full JSON Schema (via `jsonschema`) | `schema` |
| `length` | Character / word bounds | `min_length`, `max_length`, `min_words`, `max_words` |
| `format` | Output is well-formed | `kind`: `json`, `email`, `url`, `lowercase`, `uppercase` |
| `contains_all` | Output contains every listed string | `strings`, `case_sensitive` (default true) |
| `citation` | RAG-style output cites sources | `min_citations` (default 1), `pattern`, `required_sources` |
| `forbidden` | Output contains no listed string (leakage / injection guard) | `strings` |
| `numeric_close` | First number in output is within tolerance of a value | `value`, `tolerance` |
| `tool_call` | Output is JSON naming the expected tool with required args (tool-call contract) | `name`, `required_args` |
| `retrieval` | Expected doc ids appear in output; recall vs `min_recall` (failure budget) | `expected_docs`, `min_recall` (default 1.0) |

**JSON Schema (v0.2.0):** full validation via the `jsonschema`
package (Draft 2020-12), including `allOf`/`anyOf`/`oneOf`/`not`,
nested schemas, and format-independent keywords. An invalid schema
fails that expectation with a clear message instead of passing.

**Custom scorers:** register one in code with
`register_scorer(name, fn)`, or ship it via the
`prompt_eval.scorers` entry-point group. See
`examples/plugin_example.py` for a worked example.

**Citation default:** a citation is `[1]`, `[2]`, … or
`[source: name]`. Pass `pattern` to use a different marker style.

**LLM-as-judge (advisory only, v0.2.0):** add `--judge` to a run
to also ask a model to judge each output. Judge results are
reported in their own Markdown section, are never counted toward
pass rate or exit code, and a judge failure never fails the gate.
A non-deterministic judge cannot be a reproducible gate, so it
must stay advisory.

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
instead of silently passing or failing cases. Transient provider
errors (HTTP 429/5xx, network errors) are retried with backoff
(`--retries`, default 2); other HTTP errors fail immediately.

- `ollama` — a local OpenAI-compatible server, default
  `http://localhost:11434/v1`, no API key required:
  `python -m prompt_eval run --cases my-cases.yaml --provider ollama --model llama3.1`

## Diff, record/replay, and Promptfoo import

```bash
# Compare two machine-readable runs (exit 1 if any case flipped pass -> fail):
python -m prompt_eval run --cases examples/cases.yaml --provider stub --json run-baseline.json
python -m prompt_eval run --cases examples/cases.yaml --provider stub --json run-new.json
python -m prompt_eval diff --baseline run-baseline.json --new run-new.json

# Record real outputs once, re-score them offline in CI (no model call):
python -m prompt_eval record --cases examples/cases.yaml --provider openai --recording rec.json
python -m prompt_eval replay --cases examples/cases.yaml --recording rec.json

# Import a basic Promptfoo file (deterministic assertions only; model
# assertions raise an error instead of being silently dropped):
python -m prompt_eval import-promptfoo --input promptfoo.yaml --output cases.yaml
```

Token usage reported by the provider (prompt/completion/total
tokens) is shown in the Markdown report; cost is never estimated
from invented prices.

Worked example: `examples/prompt-regression/` is a realistic
6-case help-desk regression (baseline 6/6, one simulated
regression, diff names exactly that case) with its verified
output documented in its README.

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

This repo dogfoods itself: `.github/workflows/ci.yml` runs the
pytest suite and the harness on its own golden cases on every push
and pull request (Python 3.11 and 3.12). For your own repo, copy
the template below, or use the bundled `action.yml` (see below).
The essential shape is:

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

## Publishing (prepared, not yet published)

`.github/workflows/publish.yml` publishes to PyPI on version tags
via Trusted Publishing (OIDC, no token stored in the repo), and
`action.yml` already has Marketplace branding. The remaining steps
are account-owner steps only and are **not** done by this code:
create a PyPI account and enable 2FA, register a pending Trusted
Publisher for this repo/workflow on PyPI, and accept the GitHub
Marketplace Developer Agreement before publishing the Action.

## What v0.2.0 deliberately leaves out

- Hosted dashboard, SaaS, accounts, or any server component.
- Adapters for every LLM framework (LangChain, LangGraph,
  LlamaIndex, …), every language, or a visual prompt editor.
- Training, fine-tuning, dataset generation, or a prompt
  marketplace.
- A TypeScript port (a separate package later).

See [CHANGELOG.md](CHANGELOG.md) for the v0.2.0 scope,
[docs/user-guide.md](docs/user-guide.md) for the full guide, and
[CONTRIBUTING.md](CONTRIBUTING.md) for how to add a scorer.
