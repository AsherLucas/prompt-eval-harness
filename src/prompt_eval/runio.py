"""Machine-readable runs, diffing, recording, and replay.

A run JSON file is the evidence a regression harness needs: it records
every case's output and every expectation result, so a later run can be
compared against it without re-running a model. A recording is a
smaller file — just case id -> output — used to re-score real outputs
offline in CI.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import RunReport


def save_run(report: RunReport, path: Path) -> None:
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")


def load_run(path: Path) -> RunReport:
    return RunReport.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_recording(report: RunReport, path: Path) -> None:
    data = {
        "version": 1,
        "model": report.model,
        "prompt_version": report.prompt_version,
        "outputs": {r.case_id: r.output for r in report.results},
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_recording(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    outputs = data.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError(f"{path} is not a recording (no 'outputs' mapping)")
    return {str(k): str(v) for k, v in outputs.items()}


def diff_runs(baseline: RunReport, new: RunReport) -> dict:
    """Compare two runs. Returns a plain dict, easy to render or test."""
    base = {r.case_id: r for r in baseline.results}
    cur = {r.case_id: r for r in new.results}
    pass_to_fail, fail_to_pass = [], []
    for case_id in sorted(set(base) & set(cur)):
        if base[case_id].passed and not cur[case_id].passed:
            pass_to_fail.append(case_id)
        elif not base[case_id].passed and cur[case_id].passed:
            fail_to_pass.append(case_id)
    new_cases = sorted(set(cur) - set(base))
    removed_cases = sorted(set(base) - set(cur))
    return {
        "baseline_model": baseline.model,
        "new_model": new.model,
        "baseline_pass_rate": baseline.pass_rate,
        "new_pass_rate": new.pass_rate,
        "pass_to_fail": pass_to_fail,
        "fail_to_pass": fail_to_pass,
        "new_cases": new_cases,
        "removed_cases": removed_cases,
        "baseline_total": baseline.total,
        "new_total": new.total,
        "flipped": len(pass_to_fail) + len(fail_to_pass),
    }


def render_diff_markdown(diff: dict) -> str:
    def _bullets(items: list[str]) -> str:
        return "\n".join(f"- `{i}`" for i in items) if items else "- (none)"

    return "\n".join([
        "# Prompt evaluation diff",
        "",
        f"- Baseline: {diff['baseline_total']} cases, {diff['baseline_pass_rate']:.0%} passed "
        f"({diff['baseline_model'] or 'unknown model'})",
        f"- New: {diff['new_total']} cases, {diff['new_pass_rate']:.0%} passed "
        f"({diff['new_model'] or 'unknown model'})",
        f"- Flipped: {diff['flipped']} case(s)",
        "",
        "## Pass -> Fail (regressions)",
        _bullets(diff["pass_to_fail"]),
        "",
        "## Fail -> Pass (fixes)",
        _bullets(diff["fail_to_pass"]),
        "",
        "## New cases",
        _bullets(diff["new_cases"]),
        "",
        "## Removed cases",
        _bullets(diff["removed_cases"]),
        "",
    ])
