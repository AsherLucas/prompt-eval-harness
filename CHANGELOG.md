# Changelog

All notable changes to this project will be documented in this file.
The format is based on Keep a Changelog, and the project adheres to
Semantic Versioning.

## [Unreleased]

### Added

- Worked prompt-regression example (`examples/prompt-regression/`):
  6 help-desk cases, a checked-in baseline run, one simulated
  regression, and a `diff` walkthrough with verified output.
  Covered by `tests/test_prompt_regression_example.py`.
- Badges for CI status, MIT licence, and Python >= 3.11 in the
  README (no stars/downloads claimed — there are none yet).

### Fixed

- README quickstart code fence: the demo commands were outside
  the fenced block; the quickstart now uses `.venv/bin/python`
  consistently and includes a run-diff step, all verified in a
  clean venv.
- Docs drift: the scorer catalogue still described the v0.1.0
  JSON Schema subset (v0.2.0 is full Draft 2020-12 validation);
  the provider guide wrongly said there is no retry and omitted
  the keyless `ollama` provider; the user guide said Python 3.12
  is required (it is >= 3.11) and had two sections numbered 8.
- Added one-line docstrings to the main public API
  (`Case`/`CaseResult`/`RunReport`, run/recording I/O, reports,
  Promptfoo import, scorer dispatch, CLI entry points, judge).

## [0.3.0] — 2026-10-29

### Added

- New deterministic scorers: `forbidden` (fail if any listed string appears, for leakage/injection guards) and `numeric_close` (first number in output within a tolerance of an expected value).
- Tests and scorer catalogue docs for both new scorers.

## [0.2.0] — 2026-10-29

### Added

- Run-diff / baseline comparison: `--json` run files plus
  `prompt-eval diff` (pass -> fail regressions, fail -> pass fixes,
  new/removed cases; exit 1 on any regression).
- Record + replay: `prompt-eval record` saves real outputs, and
  `prompt-eval replay` re-scores them offline with no model call.
- Plugin scorers: `register_scorer()` and the
  `prompt_eval.scorers` entry-point group, with a worked example
  in `examples/plugin_example.py` and `--plugin-module` on the CLI.
- Promptfoo YAML import (`prompt-eval import-promptfoo`) for
  deterministic assertions only; unsupported assertions fail loudly.
- Advisory LLM-as-judge scorer (`--judge`): reported separately,
  never counted toward pass rate or exit code; judge failures never
  fail the gate.
- Full JSON Schema validation via the `jsonschema` package
  (replaces the v0.1.0 documented subset).
- Providers: `ollama` local-model provider (OpenAI-compatible,
  no key required), retries with backoff for transient provider
  errors, and token-usage reporting in Markdown reports.
- CI dogfood: `.github/workflows/ci.yml` runs tests and the golden
  cases on every push/PR (Python 3.11, 3.12).
- Publishing preparation: `.github/workflows/publish.yml` (PyPI
  Trusted Publishing on version tags) and Marketplace-ready
  `action.yml` branding. PyPI account/2FA, Trusted Publisher
  registration, and Marketplace agreement remain account-owner steps.
- Examples: RAG (10 cases), chatbot (10), and code generation (10)
  case files, all passing offline via the stub provider.
- Docs: full user guide, scorer catalogue, and provider guide
  under `docs/`.

### Changed

- Version bumped to 0.2.0; `RunReport` is now serialisable to/from
  JSON, and case results carry advisory results and provider usage
  separately from gate results.

## [0.1.0] — 2026-10-29

First version. Early-stage tool; no adoption is claimed.

### Added

- Python library API (`prompt_eval.run_cases`, `Case`, `Expectation`,
  `RunReport`) and CLI (`prompt-eval run` / `python -m prompt_eval run`).
- Deterministic, offline-first scorers: exact, regex, JSON-schema
  (documented subset only), length, format, contains-all, citation.
- Providers: offline stub provider; OpenAI-compatible HTTP provider
  (base URL, model, API key from environment only, never logged).
- Reports: Markdown report and JUnit XML, run metadata
  (provider/model, prompt version, harness version), non-zero exit
  code on case failure or threshold breach (CI gate).
- GitHub Action wrapper (`action.yml`, composite action).
- 30 golden example cases covering every scorer, passing offline
  via the stub provider, plus a 3-case failing example that exits 1.
- Docs: README (quickstart, scorer catalogue, CI guide),
  CONTRIBUTING, MIT LICENSE, this changelog, `pyproject.toml`.
- pytest suite covering scorers, providers, runner, reports, and CLI
  (including exit codes).
