"""Run cases through a provider and score every expectation."""

from __future__ import annotations

from .models import Case, CaseResult, ExpectationResult, RunReport
from .providers import ProviderError, StubProvider
from .scorers import score_expectation


def _usage_of(provider) -> dict:
    usage = getattr(provider, "last_usage", None)
    return dict(usage) if isinstance(usage, dict) else {}


def run_cases(
    cases: list[Case],
    provider,
    model: str = "",
    prompt_version: str = "",
    threshold: float = 1.0,
    judge=None,
) -> RunReport:
    """Run cases. ``judge`` (AdvisoryJudge or None) adds advisory
    results only — it never changes a case's pass status."""
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
        advisory = [judge.judge(case.id, prompt, output)] if judge is not None else []
        results.append(
            CaseResult(
                case_id=case.id,
                prompt=prompt,
                output=output,
                expectations=[score_expectation(output, e) for e in case.expected],
                advisory=advisory,
                usage=_usage_of(provider),
            )
        )
    return RunReport(
        results=results,
        model=model or getattr(provider, "name", ""),
        prompt_version=prompt_version,
        threshold=threshold,
    )


def replay_cases(
    cases: list[Case],
    recorded_outputs: dict[str, str],
    model: str = "replay",
    prompt_version: str = "",
    threshold: float = 1.0,
    judge=None,
) -> RunReport:
    """Score recorded outputs offline — no provider call at all."""
    results: list[CaseResult] = []
    for case in cases:
        prompt = case.rendered_prompt()
        if case.id not in recorded_outputs:
            results.append(CaseResult(
                case_id=case.id, prompt=prompt, output="",
                expectations=[ExpectationResult(
                    type="replay", passed=False,
                    detail=f"no recorded output for case {case.id!r}")],
            ))
            continue
        output = recorded_outputs[case.id]
        advisory = [judge.judge(case.id, prompt, output)] if judge is not None else []
        results.append(CaseResult(
            case_id=case.id, prompt=prompt, output=output,
            expectations=[score_expectation(output, e) for e in case.expected],
            advisory=advisory,
        ))
    return RunReport(results=results, model=model,
                     prompt_version=prompt_version, threshold=threshold)
