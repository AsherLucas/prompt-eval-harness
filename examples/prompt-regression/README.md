# Worked example: catching a prompt regression with `diff`

A help-desk assistant for a fictional product, "Northwind Cloud".
Six cases cover the checks a support answer actually needs:
a refund window that must be stated exactly, a citation to the
source policy, a reset link that must not be dropped, a structured
JSON export, a rate-limit answer, and a billing date.

This example is offline: the stub outputs stand in for model
outputs, so the whole workflow runs with no API key and no network.
In real use, replace the stub outputs with a real provider run
(see "Using a real provider" below) — the `diff` step is identical.

## Files

- `cases.yaml` — the 6 baseline cases. All 6 pass.
- `baseline.json` — the checked-in machine-readable run of
  `cases.yaml` with `--prompt-version v1`. Regenerate it after
  intentionally changing the baseline cases or prompt version:
  `python -m prompt_eval run --cases cases.yaml --provider stub --prompt-version v1 --json baseline.json`
- `regressed.yaml` — the same cases with ONE simulated change:
  the `refund-window` answer says "14 days" instead of "30 days"
  and drops its citation. This is a canned simulation, not a real
  model output, so the diff below is reproducible offline.

## Run it

From the repository root (inside the venv from the README
quickstart, or prefixing `.venv/bin/python`):

```bash
# 1. Baseline: 6/6 pass, exit 0
python -m prompt_eval run --cases examples/prompt-regression/cases.yaml \
  --provider stub --prompt-version v1 \
  --json /tmp/prompt-regression-baseline.json

# 2. Simulated new prompt version: 5/6 pass, exit 1
python -m prompt_eval run --cases examples/prompt-regression/regressed.yaml \
  --provider stub --prompt-version v2 \
  --json /tmp/prompt-regression-new.json

# 3. Diff: exit 1, because one case flipped pass -> fail
python -m prompt_eval diff \
  --baseline examples/prompt-regression/baseline.json \
  --new /tmp/prompt-regression-new.json
```

## Verified output (clean venv, prompt-eval 0.2.0)

Baseline run:

```
6/6 passed (100%, threshold 100%)
```

Regressed run:

```
5/6 passed (83%, threshold 100%)
FAIL refund-window
```

Diff (exit 1):

```
# Prompt evaluation diff

- Baseline: 6 cases, 100% passed (stub)
- New: 6 cases, 83% passed (stub)
- Flipped: 1 case(s)

## Pass -> Fail (regressions)
- `refund-window`

## Fail -> Pass (fixes)
- (none)

## New cases
- (none)

## Removed cases
- (none)
```

The gate fails on purpose here: a support answer that quietly
changes a 30-day refund window to 14 days and drops its source
citation is exactly the kind of silent degradation a regression
harness is for. Fix the prompt (or the model output), re-run,
and the diff should show no `Pass -> Fail` cases before merging.

## Using a real provider

```bash
# Remove stub_output from your copy of the cases, then:
python -m prompt_eval run --cases my-support-cases.yaml \
  --provider openai --model gpt-4o-mini --prompt-version v2 \
  --json run-v2.json
python -m prompt_eval diff --baseline baseline.json --new run-v2.json
```

Keep `baseline.json` in version control so CI can diff every
new prompt version against the last known-good run, rather than
against whatever a model happened to return yesterday.
