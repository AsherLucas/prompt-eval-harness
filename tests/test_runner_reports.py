import xml.etree.ElementTree as ET

from prompt_eval.models import Case, Expectation
from prompt_eval.providers import StubProvider
from prompt_eval.reports import render_junit, render_markdown
from prompt_eval.runner import run_cases


def _cases():
    return [
        Case(id="ok", prompt="hi", expected=[Expectation("exact", {"value": "yes"})],
             stub_output="yes"),
        Case(id="bad", prompt="hi", expected=[Expectation("exact", {"value": "yes"})],
             stub_output="no"),
    ]


def test_runner_counts_and_gate():
    r = run_cases(_cases(), StubProvider(), model="stub", prompt_version="v1", threshold=1.0)
    assert r.total == 2 and r.passed_count == 1 and r.failed_count == 1
    assert r.pass_rate == 0.5 and not r.gate_passed
    assert r.model == "stub" and r.prompt_version == "v1"
    # Lower threshold passes the same run as a gate
    r2 = run_cases(_cases(), StubProvider(), threshold=0.5)
    assert r2.gate_passed


def test_runner_prompt_substitution():
    c = Case(id="s", prompt="Hello {name}", inputs={"name": "Ada"},
             expected=[Expectation("exact", {"value": "Hello Ada"})], stub_output="Hello Ada")
    assert run_cases([c], StubProvider()).passed_count == 1


def test_markdown_report_contains_metadata_and_failures():
    md = render_markdown(run_cases(_cases(), StubProvider(), model="stub", prompt_version="v1"))
    assert "stub" in md and "v1" in md and "FAIL" in md and "bad" in md


def test_junit_report_parses_and_counts():
    xml = render_junit(run_cases(_cases(), StubProvider()))
    root = ET.fromstring(xml)
    suite = root.find("testsuite")
    assert suite.get("tests") == "2" and suite.get("failures") == "1"
    names = [tc.get("name") for tc in suite.findall("testcase")]
    assert names == ["ok", "bad"]
    bad = [tc for tc in suite.findall("testcase") if tc.get("name") == "bad"][0]
    assert bad.find("failure") is not None
