"""prompt-eval-harness: deterministic, offline-first eval regression harness."""

from .judge import AdvisoryJudge
from .models import Case, Expectation, ExpectationResult, CaseResult, RunReport
from .promptfoo import import_promptfoo
from .runio import diff_runs, load_recording, load_run, save_recording, save_run
from .runner import replay_cases, run_cases
from .scorers import load_plugin_scorers, register_scorer, score_expectation

__version__ = "0.2.0"
__all__ = [
    "Case",
    "Expectation",
    "ExpectationResult",
    "CaseResult",
    "RunReport",
    "run_cases",
    "replay_cases",
    "score_expectation",
    "register_scorer",
    "load_plugin_scorers",
    "AdvisoryJudge",
    "import_promptfoo",
    "save_run",
    "load_run",
    "save_recording",
    "load_recording",
    "diff_runs",
    "__version__",
]
