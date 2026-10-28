"""Deterministic, offline-first scorers.

Every scorer here is pure and needs no model call, no network, and no
paid API. That is deliberate: the default CI gate must be reproducible
and free. LLM-as-judge is advisory-only and lives in judge.py, never
in this gate.

Custom scorers can be registered in code with register_scorer(), or
discovered via the ``prompt_eval.scorers`` entry-point group with
load_plugin_scorers(). A plugin scorer is a function
``fn(output, params) -> ExpectationResult``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .models import Expectation, ExpectationResult

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
# Default citation markers: [1], [2], [source: ...]
_CITATION_RE = re.compile(r"\[\d+\]|\[source:[^\]]+\]", re.IGNORECASE)


def _fail(type_: str, detail: str) -> ExpectationResult:
    return ExpectationResult(type=type_, passed=False, detail=detail)


def _ok(type_: str, detail: str) -> ExpectationResult:
    return ExpectationResult(type=type_, passed=True, detail=detail)


def _score_exact(output: str, p: dict[str, Any]) -> ExpectationResult:
    expected = str(p.get("value", ""))
    case_sensitive = bool(p.get("case_sensitive", True))
    strip = bool(p.get("strip", True))
    a, b = (output, expected) if case_sensitive else (output.lower(), expected.lower())
    if strip:
        a, b = a.strip(), b.strip()
    return _ok("exact", "exact match") if a == b else _fail(
        "exact", f"expected exactly {expected!r}, got {output!r}"
    )


def _score_regex(output: str, p: dict[str, Any]) -> ExpectationResult:
    pattern = str(p.get("pattern", ""))
    flags = 0
    if p.get("ignore_case"):
        flags |= re.IGNORECASE
    if p.get("multiline"):
        flags |= re.MULTILINE
    try:
        match = re.search(pattern, output, flags)
    except re.error as exc:
        return _fail("regex", f"invalid regex {pattern!r}: {exc}")
    return _ok("regex", f"matched {pattern!r}") if match else _fail(
        "regex", f"no match for {pattern!r} in output"
    )


def _score_json_schema(output: str, p: dict[str, Any]) -> ExpectationResult:
    """Full JSON Schema validation via the ``jsonschema`` package."""
    from jsonschema import Draft202012Validator, SchemaError, ValidationError

    schema = p.get("schema", {})
    try:
        value = json.loads(output)
    except json.JSONDecodeError as exc:
        return _fail("json_schema", f"output is not valid JSON: {exc}")
    try:
        validator = Draft202012Validator(schema)
        validator.check_schema(schema)
    except SchemaError as exc:
        return _fail("json_schema", f"invalid schema: {exc.message}")
    errors = sorted(validator.iter_errors(value), key=lambda e: list(e.path))
    if not errors:
        return _ok("json_schema", "JSON matches schema")
    return _fail("json_schema", "; ".join(
        f"{'$' + ''.join('.' + str(x) for x in e.path) if e.path else '$'}: {e.message}"
        for e in errors
    ))


def _score_length(output: str, p: dict[str, Any]) -> ExpectationResult:
    chars = len(output)
    words = len(output.split())
    problems: list[str] = []
    if "min_length" in p and chars < p["min_length"]:
        problems.append(f"{chars} chars < min_length {p['min_length']}")
    if "max_length" in p and chars > p["max_length"]:
        problems.append(f"{chars} chars > max_length {p['max_length']}")
    if "min_words" in p and words < p["min_words"]:
        problems.append(f"{words} words < min_words {p['min_words']}")
    if "max_words" in p and words > p["max_words"]:
        problems.append(f"{words} words > max_words {p['max_words']}")
    return _ok("length", f"{chars} chars, {words} words") if not problems else _fail(
        "length", "; ".join(problems)
    )


def _score_format(output: str, p: dict[str, Any]) -> ExpectationResult:
    kind = str(p.get("kind", "")).lower()
    text = output.strip()
    if kind == "json":
        try:
            json.loads(text)
            return _ok("format", "valid JSON")
        except json.JSONDecodeError as exc:
            return _fail("format", f"not valid JSON: {exc}")
    if kind == "email":
        return _ok("format", "valid email") if _EMAIL_RE.match(text) else _fail(
            "format", f"{output!r} is not an email address"
        )
    if kind == "url":
        return _ok("format", "valid URL") if _URL_RE.match(text) else _fail(
            "format", f"{output!r} is not an http(s) URL"
        )
    if kind == "lowercase":
        return _ok("format", "lowercase") if text == text.lower() else _fail(
            "format", "output is not lowercase"
        )
    if kind == "uppercase":
        return _ok("format", "uppercase") if text == text.upper() else _fail(
            "format", "output is not uppercase"
        )
    return _fail("format", f"unknown format kind {kind!r} (json/email/url/lowercase/uppercase)")


def _score_contains_all(output: str, p: dict[str, Any]) -> ExpectationResult:
    strings = [str(s) for s in (p.get("strings") or [])]
    case_sensitive = bool(p.get("case_sensitive", True))
    hay = output if case_sensitive else output.lower()
    missing = [s for s in strings if (s if case_sensitive else s.lower()) not in hay]
    return _ok("contains_all", f"contains all {len(strings)} strings") if not missing else _fail(
        "contains_all", f"missing strings: {missing!r}"
    )


def _score_citation(output: str, p: dict[str, Any]) -> ExpectationResult:
    pattern = str(p.get("pattern", "")) or None
    regex = re.compile(pattern) if pattern else _CITATION_RE
    found = regex.findall(output)
    min_citations = int(p.get("min_citations", 1))
    problems: list[str] = []
    if len(found) < min_citations:
        problems.append(f"found {len(found)} citation(s), need >= {min_citations}")
    required = [str(s) for s in (p.get("required_sources") or [])]
    missing = [s for s in required if s not in output]
    if missing:
        problems.append(f"missing required sources: {missing!r}")
    return _ok("citation", f"found {len(found)} citation(s)") if not problems else _fail(
        "citation", "; ".join(problems)
    )


_SCORERS = {
    "exact": _score_exact,
    "regex": _score_regex,
    "json_schema": _score_json_schema,
    "length": _score_length,
    "format": _score_format,
    "contains_all": _score_contains_all,
    "citation": _score_citation,
}


def register_scorer(name: str, fn) -> None:
    """Register a custom scorer: fn(output, params) -> ExpectationResult."""
    _SCORERS[name] = fn


def load_plugin_scorers(group: str = "prompt_eval.scorers") -> list[str]:
    """Discover scorers from an entry-point group; returns loaded names."""
    from importlib.metadata import entry_points

    loaded: list[str] = []
    try:
        eps = entry_points(group=group)
    except TypeError:  # Python < 3.10 style API
        eps = entry_points().get(group, [])
    for ep in eps:
        fn = ep.load()
        register_scorer(ep.name, fn)
        loaded.append(ep.name)
    return loaded


def score_expectation(output: str, expectation: Expectation) -> ExpectationResult:
    fn = _SCORERS.get(expectation.type)
    if fn is None:
        return _fail(expectation.type, f"unknown scorer type {expectation.type!r}")
    return fn(output, expectation.params)
