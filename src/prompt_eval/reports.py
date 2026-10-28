"""Markdown and JUnit XML reports for a RunReport."""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from xml.dom import minidom

from .models import RunReport


def _snippet(text: str, limit: int = 300) -> str:
    text = text.replace("\n", "\\n")
    return text if len(text) <= limit else text[:limit] + "…"


def render_markdown(report: RunReport) -> str:
    lines = [
        "# Prompt evaluation report",
        "",
        f"- Model / provider: `{report.model}`",
        f"- Prompt version: `{report.prompt_version or '(not set)'}`",
        f"- Harness version: `{report.harness_version}`",
        f"- Cases: {report.total} passed, {report.failed_count} failed "
        f"({report.pass_rate:.0%} pass rate, threshold {report.threshold:.0%})",
        f"- CI gate: {'PASS' if report.gate_passed else 'FAIL'}",
        "",
        "| Case | Result | Detail |",
        "| ---- | ------ | ------ |",
    ]
    for r in report.results:
        detail = "; ".join(e.detail for e in r.expectations if not e.passed) or "all expectations passed"
        lines.append(f"| `{r.case_id}` | {'PASS' if r.passed else 'FAIL'} | {_snippet(detail)} |")
    lines.append("")
    for r in report.results:
        if r.passed:
            continue
        lines.append(f"## Failed: `{r.case_id}`")
        lines.append("")
        lines.append(f"Output: `{_snippet(r.output)}`")
        lines.append("")
        for e in r.expectations:
            if not e.passed:
                lines.append(f"- [{e.type}] {e.detail}")
        lines.append("")
    return "\n".join(lines)


def render_junit(report: RunReport) -> str:
    suites = ET.Element("testsuites")
    suite = ET.SubElement(suites, "testsuite", {
        "name": "prompt-eval",
        "tests": str(report.total),
        "failures": str(report.failed_count),
    })
    for r in report.results:
        tc = ET.SubElement(suite, "testcase", {
            "classname": "prompt_eval",
            "name": r.case_id,
        })
        for e in r.expectations:
            if not e.passed:
                failure = ET.SubElement(tc, "failure", {"message": f"[{e.type}] {e.detail}"})
                failure.text = f"output: {_snippet(r.output)}"
    rough = ET.tostring(suites, encoding="unicode")
    return minidom.parseString(rough).toprettyxml(indent="  ")
