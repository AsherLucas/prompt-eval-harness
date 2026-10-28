"""CLI: prompt-eval run --cases cases.yaml --provider stub"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from . import __version__
from .models import Case
from .providers import OpenAICompatibleProvider, StubProvider
from .reports import render_junit, render_markdown
from .runner import run_cases


def load_cases(path: Path) -> list[Case]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"cannot parse cases file {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise ValueError(f"{path} must be a YAML mapping with a 'cases' list")
    cases: list[Case] = []
    seen: set[str] = set()
    for raw in data["cases"]:
        if "id" not in raw or "prompt" not in raw:
            raise ValueError("every case needs 'id' and 'prompt'")
        if raw["id"] in seen:
            raise ValueError(f"duplicate case id {raw['id']!r}")
        seen.add(raw["id"])
        cases.append(Case.from_dict(raw))
    if not cases:
        raise ValueError("no cases found")
    return cases


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="prompt-eval", description="Prompt & agent evaluation regression harness")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run cases and report pass/fail")
    run.add_argument("--cases", required=True, help="YAML case file")
    run.add_argument("--provider", choices=["stub", "openai"], default="stub")
    run.add_argument("--base-url", default="https://api.openai.com/v1",
                     help="OpenAI-compatible base URL (openai provider only)")
    run.add_argument("--model", default="gpt-4o-mini",
                     help="model name for the openai provider (also recorded in reports)")
    run.add_argument("--api-key-env", default="OPENAI_API_KEY",
                     help="env var holding the API key (never pass a key on the CLI)")
    run.add_argument("--prompt-version", default="")
    run.add_argument("--threshold", type=float, default=1.0,
                     help="minimum pass rate for the CI gate, 0.0-1.0 (default 1.0)")
    run.add_argument("--markdown", default="", help="write Markdown report to this path")
    run.add_argument("--junit", default="", help="write JUnit XML report to this path")
    run.add_argument("--quiet", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "run":
        return 2
    if not 0.0 <= args.threshold <= 1.0:
        print("error: --threshold must be between 0.0 and 1.0", file=sys.stderr)
        return 2
    try:
        cases = load_cases(Path(args.cases))
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.provider == "stub":
        provider = StubProvider()
        model = "stub"
    else:
        provider = OpenAICompatibleProvider(
            base_url=args.base_url, model=args.model, api_key_env=args.api_key_env
        )
        model = args.model
    report = run_cases(cases, provider, model=model,
                       prompt_version=args.prompt_version, threshold=args.threshold)
    if not args.quiet:
        print(f"{report.passed_count}/{report.total} passed "
              f"({report.pass_rate:.0%}, threshold {args.threshold:.0%})")
        for r in report.results:
            if not r.passed:
                print(f"FAIL {r.case_id}")
    if args.markdown:
        Path(args.markdown).write_text(render_markdown(report), encoding="utf-8")
    if args.junit:
        Path(args.junit).write_text(render_junit(report), encoding="utf-8")
    return 0 if report.gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
