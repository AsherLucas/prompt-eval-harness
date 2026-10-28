# Contributing

Thank you for considering a contribution. This project is early-stage
(see the honest-status note in README.md); small, well-tested
contributions are welcome, and scope discipline matters more than
feature count.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```

## Adding a scorer

1. Add a `_score_<name>` function in `src/prompt_eval/scorers.py`
   that takes `(output, params)` and returns an `ExpectationResult`.
   Keep it deterministic and offline — no model calls, no network.
2. Register it in the `_SCORERS` dict in the same file.
3. Document it in the scorer catalogue in README.md, including
   every parameter and its default.
4. Add unit tests in `tests/test_scorers.py` covering at least one
   pass, one fail, and any parameter that changes behaviour.
5. Add at least one golden case in `examples/cases.yaml` if the
   scorer is user-facing, and keep the golden file passing with
   `--provider stub`.

## Other contributions

- Bug fixes: include a failing test first if you can.
- Docs: the quickstart must stay runnable in under five minutes.
- Do not add a dependency without a reason in the PR description;
  the project intentionally keeps dependencies minimal (PyYAML +
  stdlib, pytest for tests).
- Do not add a hosted service, an account system, or a feature
  listed under "What v1 deliberately leaves out" in README.md
  without discussing it in an issue first.

## Releases

Releases are versioned with semantic versioning and noted in
CHANGELOG.md. A release means: tests pass, the golden example run
passes offline, and the failing example still exits non-zero.
