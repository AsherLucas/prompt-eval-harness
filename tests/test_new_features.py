"""Tests for v0.2.0 features: diff, record/replay, plugins, Promptfoo,
full JSON Schema, advisory judge, Ollama provider, retries."""

import json
from pathlib import Path

import pytest

from prompt_eval import Case, Expectation, run_cases, replay_cases, diff_runs, save_run, load_run
from prompt_eval.cli import main as cli_main
from prompt_eval.judge import AdvisoryJudge
from prompt_eval.models import ExpectationResult
from prompt_eval.promptfoo import import_promptfoo
from prompt_eval.providers import OllamaCompatibleProvider, OpenAICompatibleProvider, StubProvider
from prompt_eval.runio import load_recording, render_diff_markdown, save_recording
from prompt_eval.scorers import register_scorer, score_expectation


def _case(cid, expected, stub):
    return Case(id=cid, prompt="p", expected=[Expectation.from_dict(e) for e in expected],
                stub_output=stub)


def test_diff_reports_pass_to_fail(tmp_path):
    cases = [_case("a", [{"type": "exact", "value": "hi"}], "hi"),
             _case("b", [{"type": "exact", "value": "yo"}], "yo")]
    good = run_cases(cases, StubProvider())
    bad_cases = [_case("a", [{"type": "exact", "value": "hi"}], "bye"),
                 _case("b", [{"type": "exact", "value": "yo"}], "yo")]
    bad = run_cases(bad_cases, StubProvider())
    diff = diff_runs(good, bad)
    assert diff["pass_to_fail"] == ["a"]
    assert diff["fail_to_pass"] == []
    assert "a" in render_diff_markdown(diff)


def test_record_and_replay(tmp_path):
    cases = [_case("a", [{"type": "exact", "value": "hi"}], "hi")]
    report = run_cases(cases, StubProvider())
    rec = tmp_path / "rec.json"
    save_recording(report, rec)
    assert load_recording(rec) == {"a": "hi"}
    replayed = replay_cases(cases, load_recording(rec))
    assert replayed.passed_count == 1
    missing = replay_cases(cases, {})
    assert missing.passed_count == 0


def test_run_json_roundtrip(tmp_path):
    report = run_cases([_case("a", [{"type": "exact", "value": "hi"}], "hi")], StubProvider())
    path = tmp_path / "run.json"
    save_run(report, path)
    loaded = load_run(path)
    assert loaded.passed_count == 1 and loaded.results[0].output == "hi"


def test_plugin_scorer():
    register_scorer("is_even_length_test", lambda out, p: ExpectationResult(
        type="is_even_length_test", passed=len(out) % 2 == 0, detail="even" if len(out) % 2 == 0 else "odd"))
    assert score_expectation("abcd", Expectation(type="is_even_length_test")).passed
    assert not score_expectation("abc", Expectation(type="is_even_length_test")).passed


def test_promptfoo_import(tmp_path):
    path = tmp_path / "pf.yaml"
    path.write_text(
        "prompts:\n  - 'Say hello to {{name}}'\n"
        "tests:\n  - vars: {name: Ada}\n"
        "    assert:\n      - type: contains\n        value: Ada\n"
        "      - type: regex\n        value: '^Say'\n",
        encoding="utf-8")
    cases = import_promptfoo(path)
    assert len(cases) == 1
    assert cases[0].prompt == "Say hello to Ada"
    assert [e.type for e in cases[0].expected] == ["contains_all", "regex"]
    # Unsupported (model) assertions must fail loudly, not be dropped.
    bad = tmp_path / "bad.yaml"
    bad.write_text("prompts: ['x']\ntests:\n  - vars: {}\n    assert:\n      - type: llm-rubric\n        value: good\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        import_promptfoo(bad)


def test_full_json_schema():
    schema = {"allOf": [{"type": "object", "required": ["a"]},
                        {"properties": {"a": {"type": "integer", "minimum": 5}}}],
              "properties": {"a": {"type": "integer"}},
              "additionalProperties": False}
    assert score_expectation('{"a": 7}', Expectation(type="json_schema", params={"schema": schema})).passed
    assert not score_expectation('{"a": 2}', Expectation(type="json_schema", params={"schema": schema})).passed
    assert not score_expectation('{"a": 7, "b": 1}', Expectation(type="json_schema", params={"schema": schema})).passed
    # anyOf / not are beyond the old subset and must now work.
    schema2 = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
    assert score_expectation('"x"', Expectation(type="json_schema", params={"schema": schema2})).passed
    assert not score_expectation('1.5', Expectation(type="json_schema", params={"schema": schema2})).passed
    bad_schema = {"type": "no-such-type"}
    assert not score_expectation('"x"', Expectation(type="json_schema", params={"schema": bad_schema})).passed


def test_advisory_judge_never_changes_gate():
    judge_provider = StubProvider({"judge:a": json.dumps({"verdict": "fail", "reason": "too short"})})
    judge = AdvisoryJudge(judge_provider)
    cases = [_case("a", [{"type": "exact", "value": "hi"}], "hi")]
    report = run_cases(cases, StubProvider(), judge=judge)
    assert report.passed_count == 1 and report.gate_passed
    assert report.results[0].advisory[0].type == "llm_judge_advisory"
    assert not report.results[0].advisory[0].passed
    # Judge failure is advisory-only too.
    broken = AdvisoryJudge(StubProvider({}))
    report2 = run_cases(cases, StubProvider(), judge=broken)
    assert report2.gate_passed


def test_ollama_provider_no_key_required(monkeypatch):
    import urllib.request

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(
            {"choices": [{"message": {"content": "hello"}}], "usage": {"total_tokens": 9}}).encode()

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: Resp())
    provider = OllamaCompatibleProvider(base_url="http://localhost:11434/v1", model="test-model")
    assert provider.complete("a", "hi") == "hello"
    assert provider.last_usage["total_tokens"] == 9


def test_openai_retries_on_503_then_succeeds(monkeypatch):
    import urllib.error
    import urllib.request

    calls = {"n": 0}

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError(req.full_url, 503, "unavailable", {}, None)
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("TEST_KEY_X", "secret")
    provider = OpenAICompatibleProvider(base_url="https://example.invalid/v1", model="m",
                                        api_key_env="TEST_KEY_X", max_retries=3)
    assert provider.complete("a", "hi") == "ok"
    assert calls["n"] == 3


def test_cli_diff_record_replay(tmp_path):
    cases_file = tmp_path / "cases.yaml"
    cases_file.write_text(
        "cases:\n  - id: a\n    prompt: hi\n    stub_output: hi\n"
        "    expected:\n      - type: exact\n        value: hi\n", encoding="utf-8")
    rec = tmp_path / "rec.json"
    assert cli_main(["record", "--cases", str(cases_file), "--provider", "stub",
                     "--recording", str(rec), "--quiet"]) == 0
    assert json.loads(rec.read_text())["outputs"] == {"a": "hi"}
    assert cli_main(["replay", "--cases", str(cases_file), "--recording", str(rec), "--quiet"]) == 0
    run1 = tmp_path / "run1.json"
    assert cli_main(["run", "--cases", str(cases_file), "--provider", "stub",
                     "--json", str(run1), "--quiet"]) == 0
    assert cli_main(["diff", "--baseline", str(run1), "--new", str(run1)]) == 0
