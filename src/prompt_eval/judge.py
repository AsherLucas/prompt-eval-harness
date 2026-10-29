"""Advisory LLM-as-judge scoring.

This is deliberately NOT part of the deterministic CI gate. A judge
result is reported separately, is never counted toward pass rate or
exit code, and is only as good as the judge model on that day. If the
judge call fails or its reply cannot be parsed, the advisory result
says so instead of failing the case.
"""

from __future__ import annotations

import json

from .models import ExpectationResult


class AdvisoryJudge:
    """Ask a provider model to judge an output, advisory-only."""

    def __init__(self, provider, model: str = ""):
        self.provider = provider
        self.model = model or getattr(provider, "name", "")

    def judge(self, case_id: str, prompt: str, output: str) -> ExpectationResult:
        """Judge one output; failures return an advisory result, never a gate failure."""
        judge_prompt = (
            "You are a strict evaluator. Judge whether the OUTPUT satisfies the TASK.\n"
            "Reply with JSON only, exactly: {\"verdict\": \"pass\" or \"fail\", "
            "\"reason\": \"one short sentence\"}.\n"
            f"TASK: {prompt}\nOUTPUT: {output}"
        )
        try:
            reply = self.provider.complete(f"judge:{case_id}", judge_prompt)
            verdict = json.loads(reply)
            passed = str(verdict.get("verdict", "")).lower() == "pass"
            return ExpectationResult(
                type="llm_judge_advisory",
                passed=passed,
                detail=f"advisory judge ({self.model}): {verdict.get('reason', '') or verdict.get('verdict', '')}".strip(),
            )
        except Exception as exc:  # judge failure must never fail the gate
            # passed=False here is an advisory signal only; advisory
            # results are stored separately and never change case pass
            # status, pass rate, or exit code.
            return ExpectationResult(
                type="llm_judge_advisory",
                passed=False,
                detail=f"advisory judge unavailable (not counted): {exc}",
            )
