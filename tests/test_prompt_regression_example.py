"""The worked prompt-regression example must stay reproducible.

Baseline cases pass 6/6; the simulated regressed file passes 5/6
with exactly one pass -> fail flip (refund-window); diffing the
checked-in baseline against the regressed run reports that flip
and no others. This guards the example's README claims.
"""

from pathlib import Path

from prompt_eval.cli import load_cases
from prompt_eval.providers import StubProvider
from prompt_eval.runio import diff_runs, load_run
from prompt_eval.runner import run_cases

EXAMPLES = Path(__file__).parent.parent / "examples" / "prompt-regression"


def test_baseline_cases_pass():
    cases = load_cases(EXAMPLES / "cases.yaml")
    assert len(cases) == 6
    report = run_cases(cases, StubProvider())
    assert report.passed_count == 6
    assert report.gate_passed


def test_regressed_cases_flip_only_refund_window():
    cases = load_cases(EXAMPLES / "regressed.yaml")
    report = run_cases(cases, StubProvider())
    assert report.passed_count == 5
    assert not report.gate_passed
    failed = [r.case_id for r in report.results if not r.passed]
    assert failed == ["refund-window"]


def test_diff_against_checked_in_baseline():
    baseline = load_run(EXAMPLES / "baseline.json")
    assert baseline.passed_count == 6
    regressed = run_cases(load_cases(EXAMPLES / "regressed.yaml"), StubProvider())
    diff = diff_runs(baseline, regressed)
    assert diff["pass_to_fail"] == ["refund-window"]
    assert diff["fail_to_pass"] == []
    assert diff["new_cases"] == []
    assert diff["removed_cases"] == []
