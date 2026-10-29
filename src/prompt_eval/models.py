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
    """One evaluation case: a prompt, optional inputs, and its checks."""

    id: str
    prompt: str
    inputs: dict[str, Any] = field(default_factory=dict)
    expected: list[Expectation] = field(default_factory=list)
    stub_output: str | None = None
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Case":
        """Build a Case from a case-file mapping."""
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
    """The outcome of one scorer check on one output."""

    type: str
    passed: bool
    detail: str


@dataclass
class CaseResult:
    """The scored outcome of one case (advisory results excluded from pass)."""

    case_id: str
    prompt: str
    output: str
    expectations: list[ExpectationResult] = field(default_factory=list)
    # Advisory results (e.g. LLM-as-judge) are NEVER part of `passed`.
    advisory: list[ExpectationResult] = field(default_factory=list)
    # Provider usage for this case, e.g. {"prompt_tokens": 12,
    # "completion_tokens": 4, "total_tokens": 16}. Empty when the
    # provider does not report usage (stub, most local models).
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """True only if every (non-advisory) expectation passed."""
        return all(e.passed for e in self.expectations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "prompt": self.prompt,
            "output": self.output,
            "passed": self.passed,
            "expectations": [
                {"type": e.type, "passed": e.passed, "detail": e.detail}
                for e in self.expectations
            ],
            "advisory": [
                {"type": e.type, "passed": e.passed, "detail": e.detail}
                for e in self.advisory
            ],
            "usage": self.usage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CaseResult":
        return cls(
            case_id=str(data["case_id"]),
            prompt=str(data.get("prompt", "")),
            output=str(data.get("output", "")),
            expectations=[
                ExpectationResult(type=e["type"], passed=bool(e["passed"]), detail=str(e.get("detail", "")))
                for e in data.get("expectations") or []
            ],
            advisory=[
                ExpectationResult(type=e["type"], passed=bool(e["passed"]), detail=str(e.get("detail", "")))
                for e in data.get("advisory") or []
            ],
            usage=dict(data.get("usage") or {}),
        )


@dataclass
class RunReport:
    """A whole run: every case result, plus gate and pass-rate views."""

    results: list[CaseResult] = field(default_factory=list)
    model: str = ""
    prompt_version: str = ""
    harness_version: str = "0.2.0"
    threshold: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "harness_version": self.harness_version,
            "threshold": self.threshold,
            "total": self.total,
            "passed_count": self.passed_count,
            "pass_rate": self.pass_rate,
            "gate_passed": self.gate_passed,
            "results": [r.to_dict() for r in self.results],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunReport":
        return cls(
            results=[CaseResult.from_dict(r) for r in data.get("results") or []],
            model=str(data.get("model", "")),
            prompt_version=str(data.get("prompt_version", "")),
            harness_version=str(data.get("harness_version", "")),
            threshold=float(data.get("threshold", 1.0)),
        )

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
