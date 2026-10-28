"""Example custom scorer, registered via an entry point or module import.

To use it in your own package, add this to your pyproject.toml:

    [project.entry-points."prompt_eval.scorers"]
    starts_with = "my_package.scorers:score_starts_with"

or, for a quick local run, import the module with
``--plugin-module`` (the import registers the scorer):

    python -m prompt_eval run --cases my-cases.yaml --provider stub \\
        --plugin-module my_package.scorers

Then use ``type: starts_with`` with ``params: {prefix: "..."}`` in a
case file, exactly like a built-in scorer.
"""

from prompt_eval.models import ExpectationResult


def score_starts_with(output: str, params: dict) -> ExpectationResult:
    prefix = str(params.get("prefix", ""))
    if output.startswith(prefix):
        return ExpectationResult(type="starts_with", passed=True, detail=f"starts with {prefix!r}")
    return ExpectationResult(
        type="starts_with", passed=False, detail=f"does not start with {prefix!r}"
    )


# Register on import so --plugin-module works without packaging.
try:
    from prompt_eval.scorers import register_scorer

    register_scorer("starts_with", score_starts_with)
except Exception:
    pass
