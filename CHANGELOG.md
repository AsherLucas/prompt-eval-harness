# Changelog

All notable changes to this project will be documented in this file.
The format is based on Keep a Changelog, and the project adheres to
Semantic Versioning.

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
