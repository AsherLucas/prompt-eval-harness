"""Data models for cases, expectations, and run results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Expectation:
    """One check applied to a model output.

    ``type`` is one of: exact, regex, json_schema, length, format,
    contains_all, citation. Remaining keys are scorer-specific and are
    kept in ``params`` so new scorers do not need a model change.
    """

    type: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Expectation":
        data = dict(data)
        type_ = data.pop("type")
        return cls(type=type_, params=data)


@dataclass
class Case:
    id: str
    prompt: str
    inputs: dict[str, Any] = field(default_factory=dict)
    expected: list[Expectation] = field(default_factory=list)
    stub_output: str | None = None
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Case":
        return cls(
            id=str(data["id"]),
            prompt=str(data.get("prompt", "")),
            inputs=dict(data.get("inputs") or {}),
            expected=[Expectation.from_dict(e) for e in (data.get("expected") or [])],
            stub_output=data.get("stub_output"),
            tags=list(data.get("tags") or []),
        )

    def rendered_prompt(self) -> str:
        """Substitute ``{name}`` placeholders from ``inputs``.

        Unknown placeholders are left untouched instead of raising, so a
        case file typo fails loudly as a scorer failure later, not as a
        crash in prompt rendering.
        """
        out = self.prompt
        for key, value in self.inputs.items():
            out = out.replace("{" + str(key) + "}", str(value))
        return out


@dataclass
class ExpectationResult:
    type: str
    passed: bool
    detail: str


@dataclass
class CaseResult:
    case_id: str
    prompt: str
    output: str
    expectations: list[ExpectationResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(e.passed for e in self.expectations)


@dataclass
class RunReport:
    results: list[CaseResult] = field(default_factory=list)
    model: str = ""
    prompt_version: str = ""
    harness_version: str = "0.1.0"
    threshold: float = 1.0

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_count(self) -> int:
        return self.total - self.passed_count

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.total if self.total else 0.0

    @property
    def gate_passed(self) -> bool:
        return self.total > 0 and self.pass_rate >= self.threshold
