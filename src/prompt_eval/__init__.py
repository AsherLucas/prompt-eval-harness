"""prompt-eval-harness: deterministic, offline-first eval regression harness."""

from .models import Case, Expectation, ExpectationResult, CaseResult, RunReport
from .runner import run_cases
from .scorers import score_expectation

__version__ = "0.1.0"
__all__ = [
    "Case",
    "Expectation",
    "ExpectationResult",
    "CaseResult",
    "RunReport",
    "run_cases",
    "score_expectation",
    "__version__",
]
