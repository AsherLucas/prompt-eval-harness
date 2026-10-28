"""Run cases through a provider and score every expectation."""

from __future__ import annotations

from .models import Case, CaseResult, ExpectationResult, RunReport
from .providers import ProviderError, StubProvider
from .scorers import score_expectation


def run_cases(
    cases: list[Case],
    provider,
    model: str = "",
    prompt_version: str = "",
    threshold: float = 1.0,
) -> RunReport:
    results: list[CaseResult] = []
    for case in cases:
        prompt = case.rendered_prompt()
        try:
            if isinstance(provider, StubProvider) and case.stub_output is not None:
                output = case.stub_output
            else:
                output = provider.complete(case.id, prompt)
        except ProviderError as exc:
            output = ""
            results.append(
                CaseResult(
                    case_id=case.id,
                    prompt=prompt,
                    output=output,
                    expectations=[
                        # Surface a provider failure as a failed case,
                        # not a crash, so CI reports it as a failure.
                        ExpectationResult(type="provider", passed=False, detail=str(exc))
                    ],
                )
            )
            continue
        results.append(
            CaseResult(
                case_id=case.id,
                prompt=prompt,
                output=output,
                expectations=[score_expectation(output, e) for e in case.expected],
            )
        )
    return RunReport(
        results=results,
        model=model or getattr(provider, "name", ""),
        prompt_version=prompt_version,
        threshold=threshold,
    )
