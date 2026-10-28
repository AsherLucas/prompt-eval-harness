"""Import basic Promptfoo YAML case files.

Supported, and only supported:
- ``prompts``: a string, or a list of strings. Each prompt becomes a
  case (one case per prompt x test).
- ``tests``: a list, each with ``vars`` (substituted into ``{{var}}``
  and ``{var}`` placeholders) and ``assert``.
- Deterministic assertions only: ``equals`` -> exact, ``contains``
  -> contains_all, ``regex`` -> regex, ``is-json`` -> format json,
  ``contains-json`` -> format json, ``icontains`` -> contains_all
  (case-insensitive).

Not supported, by design: providers, model/LLM-judge assertions,
``assert`` entries without a ``type``, transforms, variables files,
and anything that needs a model call. Unsupported assertions raise
ValueError naming the assertion, instead of being silently dropped —
silently dropping an assertion would make a passing run lie.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Case, Expectation

_ASSERT_MAP = {
    "equals": lambda a: Expectation(type="exact", params={"value": str(a.get("value", ""))}),
    "contains": lambda a: Expectation(type="contains_all", params={"strings": [str(a.get("value", ""))]}),
    "icontains": lambda a: Expectation(
        type="contains_all", params={"strings": [str(a.get("value", ""))], "case_sensitive": False}
    ),
    "regex": lambda a: Expectation(type="regex", params={"pattern": str(a.get("value", ""))}),
    "is-json": lambda a: Expectation(type="format", params={"kind": "json"}),
    "contains-json": lambda a: Expectation(type="format", params={"kind": "json"}),
}


def _render_prompt(prompt: str, vars_: dict) -> str:
    out = prompt
    for key, value in vars_.items():
        out = out.replace("{{" + str(key) + "}}", str(value))
        out = out.replace("{" + str(key) + "}", str(value))
    return out


def import_promptfoo(path: Path) -> list[Case]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"cannot parse Promptfoo file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a Promptfoo YAML mapping")
    prompts = data.get("prompts")
    if isinstance(prompts, str):
        prompts = [prompts]
    if not isinstance(prompts, list) or not prompts:
        raise ValueError(f"{path} needs a non-empty 'prompts' list or string")
    tests = data.get("tests")
    if not isinstance(tests, list) or not tests:
        raise ValueError(f"{path} needs a non-empty 'tests' list")
    cases: list[Case] = []
    for ti, test in enumerate(tests):
        if not isinstance(test, dict):
            raise ValueError(f"test {ti} in {path} must be a mapping")
        vars_ = dict(test.get("vars") or {})
        expected: list[Expectation] = []
        for assertion in test.get("assert") or []:
            if not isinstance(assertion, dict) or "type" not in assertion:
                raise ValueError(f"unsupported assertion in test {ti}: {assertion!r} (assertions need a 'type')")
            fn = _ASSERT_MAP.get(str(assertion["type"]))
            if fn is None:
                raise ValueError(
                    f"unsupported Promptfoo assertion type {assertion['type']!r} in test {ti}; "
                    "only deterministic assertions are imported (equals, contains, icontains, "
                    "regex, is-json, contains-json)"
                )
            expected.append(fn(assertion))
        for pi, prompt in enumerate(prompts):
            cases.append(Case(
                id=f"promptfoo-{ti}" + (f"-p{pi}" if len(prompts) > 1 else ""),
                prompt=_render_prompt(str(prompt), vars_),
                inputs=vars_,
                expected=list(expected),
                tags=["promptfoo"],
            ))
    return cases


def cases_to_yaml(cases: list[Case]) -> str:
    out = {"version": 1, "cases": []}
    for c in cases:
        out["cases"].append({
            "id": c.id,
            "prompt": c.prompt,
            "inputs": c.inputs,
            "expected": [{"type": e.type, **e.params} for e in c.expected],
            "tags": c.tags,
        })
    return yaml.safe_dump(out, sort_keys=False, allow_unicode=True)
