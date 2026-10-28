# prompt-eval-harness user guide (v0.2.0)

> **Honest status: this is an early-stage tool.** It has no stars,
> downloads, or users claimed, and it does **not yet qualify for
> any six-month maintainer programme** (such as OpenAI Codex for
> Open Source or Anthropic Claude for Open Source, which reward
> already widely-used open-source projects). Everything below
> describes what v0.2.0 actually does. There is still no published
> PyPI package yet — see the README for the account-only publishing
> steps that remain.

## 1. Installing from a clean virtual environment

You need Python 3.12 (see the CI example in the README) and no API
key for the offline path. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
# Then either activate the venv, or prefix every command:
# .venv/bin/python -m prompt_eval ...
```

On externally-managed systems such as Debian/Ubuntu, the virtual
environment is required: system `pip` refuses package installs
outside one. There is no PyPI package yet, so install from a
checkout of this repository, not from `pip install prompt-eval-harness`.

Check the install worked:

```bash
python -m prompt_eval --version
```

## 2. Writing a case file

A case file is a YAML mapping with a `cases` list. Every case needs
an `id` (unique within the file — duplicates are a config error)
and a `prompt`. Each case also has an `expected` list of scorer
checks, and optionally `inputs` and `stub_output`.

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

Notes that matter in practice:

- `inputs` are substituted into `{placeholders}` in the prompt
  before the provider is called. An unknown placeholder is left
  untouched rather than raising, so a typo surfaces later as a
  scorer failure, not a crash.
- `stub_output` is for offline demos only. It is the canned output
  the stub provider returns for that case. In real use, remove
  `stub_output` and run against a real provider, so outputs come
  from a model, not from the case file. A stub run proves the
  harness works; it does **not** prove a model is good.
- A case passes only if **every** expectation in its `expected`
  list passes. You can combine scorers on one case (for example a
  `contains_all` check plus a `length` check).
- An unknown scorer `type` does not crash the run: that expectation
  fails with an "unknown scorer type" detail, which fails the case.
- See [scorer-catalogue.md](scorer-catalogue.md) for every scorer
  and its parameters, and [provider-guide.md](provider-guide.md)
  for providers.

Ready-made examples live in `examples/`:

- `examples/cases.yaml` — 30 golden cases covering every scorer.
- `examples/rag.yaml` — retrieval-augmented generation cases built
  around the `citation` scorer.
- `examples/chatbot.yaml` — chatbot-reply cases built around
  `format`, `length`, and `contains_all`.
- `examples/codegen.yaml` — code/structured-output cases built
  around `json_schema`, `regex`, and `exact`.

## 3. Running offline with the stub provider

No API key, no network:

```bash
python -m prompt_eval run --cases examples/cases.yaml --provider stub
```

Expected output for the golden file is `30/30 passed (100%,
threshold 100%)`. Failing cases are listed as `FAIL <case-id>` on
stdout. Add `--quiet` to suppress the per-run summary.

To see what a failing gate looks like on purpose, the repo ships
`examples/failing.yaml`:

```bash
python -m prompt_eval run --cases examples/failing.yaml --provider stub; echo "exit=$?"
```

## 4. Running with an OpenAI-compatible provider

The `openai` provider talks to any OpenAI-compatible
`/chat/completions` endpoint. The API key is read from an
environment variable at run time — never put a key in a case file,
on the command line, or in a log.

```bash
export OPENAI_API_KEY="..."   # from your provider, never commit it
python -m prompt_eval run --cases my-cases.yaml --provider openai \
  --model gpt-4o-mini --prompt-version v3
```

The defaults are `--base-url https://api.openai.com/v1`,
`--model gpt-4o-mini`, and `--api-key-env OPENAI_API_KEY`. To use a
different endpoint or key variable, change the flags, not the file:

```bash
python -m prompt_eval run --cases my-cases.yaml --provider openai \
  --base-url https://my-host.example/v1 --api-key-env MY_API_KEY_ENV
```

If the named environment variable is unset, the run does not
silently pass or fail cases: each case records a `provider`
failure with a clear message, and the gate fails (exit code 1).
The same happens for an unreachable endpoint or an unexpected
response shape. `--prompt-version` is recorded in reports so you
can tell runs apart when a prompt changes; it does not change
scoring. Full provider detail, including local OpenAI-compatible
endpoints, is in [provider-guide.md](provider-guide.md).

## 5. Reading the Markdown and JUnit reports

Add `--markdown` and/or `--junit` to write reports alongside the
console summary:

```bash
python -m prompt_eval run --cases examples/cases.yaml --provider stub \
  --markdown report.md --junit report.xml
```

### Markdown report (`--markdown report.md`)

- A header with the model/provider name, prompt version (or
  "(not set)"), harness version, total/passed/failed counts, pass
  rate, threshold, and an overall `CI gate: PASS/FAIL` line.
- A summary table with one row per case: case id, `PASS`/`FAIL`,
  and a detail column (the failing expectation details, or "all
  expectations passed"). Long outputs and details are truncated
  to 300 characters with an ellipsis, and newlines are escaped.
- One `## Failed: <case-id>` section per failed case, showing the
  (truncated) output and one bullet per failed expectation in the
  form `- [<scorer-type>] <detail>`. Passing cases get no section,
  so a passing report is just the header and the table.

### JUnit report (`--junit report.xml`)

Standard JUnit XML with a single `testsuite` named `prompt-eval`
and one `testcase` per case (`classname="prompt_eval"`,
`name="<case-id>"`). Each failed expectation becomes a `failure`
element on that case, with the scorer detail in its `message`
attribute and the (truncated) output as its text. CI systems that
understand JUnit can therefore display failures per case. Passing
cases have no `failure` element.

## 6. Using thresholds

`--threshold` is the minimum pass rate for the CI gate, from `0.0`
to `1.0`. The default is `1.0`: every case must pass.

```bash
# Allow a 90% pass rate (use consciously — see below):
python -m prompt_eval run --cases my-cases.yaml --provider stub --threshold 0.9
```

Prefer `1.0` for a regression gate. A threshold below `1.0` lets
regressions through by design: with `--threshold 0.9` and 10
cases, one failing case still passes the gate. A threshold outside
`0.0–1.0` is a usage error (exit code 2), not a passing run.

## 7. Exit codes

| Code | Meaning |
| ---- | ------- |
| `0` | Gate passed (pass rate >= `--threshold`). |
| `1` | A case failed, the threshold was breached, or the provider failed. |
| `2` | Usage/config error: bad or unparseable case file, duplicate case id, a case missing `id` or `prompt`, an empty case list, or a threshold out of range. |

In shell scripts, check the exit code rather than grepping the
summary line: `python -m prompt_eval run ... || echo "gate failed"`.

## 8. Using the harness in CI

The essential shape, also shown in the README, is: install, run
with the stub provider (or a real provider with a secret), and
upload the reports even when the gate fails so failures stay
visible:

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

Tips for CI use:

- The bundled `action.yml` is a composite action wrapping the same
  steps, so a consumer repo can call it with `cases`, `provider`,
  `threshold`, and report-path inputs (see `action.yml`).
- Keep the default `--threshold 1.0` for a regression gate, and
  lower it only deliberately, as described in section 6.
- Never put an API key in a workflow file or a case file. Pass it
  as a secret into the environment variable named by
  `--api-key-env` (default `OPENAI_API_KEY`).
- The stub provider is the right choice for a CI smoke run: it is
  offline and free. It does not evaluate a real model, so pair it
  with a real-provider run (on a schedule, or on selected refs)
  if you want model-quality signal.
- A provider failure in CI is a failed gate (exit code 1), not a
  skipped run — treat it as a broken run to investigate, not as a
  pass.

## 8. v0.2.0 workflows: diff, record/replay, Promptfoo import, advisory judge

```bash
# Save a machine-readable run, then compare a later run against it.
python -m prompt_eval run --cases examples/cases.yaml --provider stub --json run-baseline.json
python -m prompt_eval run --cases examples/cases.yaml --provider stub --json run-new.json
python -m prompt_eval diff --baseline run-baseline.json --new run-new.json

# Record real outputs once, then re-score them offline in CI (no model call).
python -m prompt_eval record --cases examples/cases.yaml --provider openai --recording rec.json
python -m prompt_eval replay --cases examples/cases.yaml --recording rec.json

# Convert a basic Promptfoo file (deterministic assertions only).
python -m prompt_eval import-promptfoo --input promptfoo.yaml --output cases.yaml

# Advisory judge: reported separately, never counts toward the gate.
python -m prompt_eval run --cases examples/cases.yaml --provider stub --judge --judge-provider openai
```

The judge needs a real provider (its default is the OpenAI-compatible
provider); with `--provider stub` alone and no judge flags, no judge
runs. Token usage is reported from the provider when it returns it;
cost is never estimated from invented prices.
