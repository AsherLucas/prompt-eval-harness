"""CLI: prompt-eval run | diff | record | replay | import-promptfoo"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

import yaml

from . import __version__
from .judge import AdvisoryJudge
from .models import Case
from .promptfoo import cases_to_yaml, import_promptfoo
from .providers import OllamaCompatibleProvider, OpenAICompatibleProvider, StubProvider
from .reports import render_junit, render_markdown
from .runio import diff_runs, load_recording, load_run, render_diff_markdown, save_recording, save_run
from .runner import replay_cases, run_cases
from .scorers import load_plugin_scorers


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


def _load_plugins(args) -> None:
    for mod in getattr(args, "plugin_module", []) or []:
        importlib.import_module(mod)
    load_plugin_scorers()


def _make_provider(args):
    if args.provider == "stub":
        return StubProvider(), "stub"
    if args.provider == "ollama":
        return OllamaCompatibleProvider(
            base_url=args.base_url, model=args.model, max_retries=args.retries), f"ollama:{args.model}"
    return OpenAICompatibleProvider(
        base_url=args.base_url, model=args.model, api_key_env=args.api_key_env,
        max_retries=args.retries), args.model


def _make_judge(args):
    if not getattr(args, "judge", False):
        return None
    provider, model = _make_provider(
        argparse.Namespace(provider=args.judge_provider, base_url=args.judge_base_url,
                           model=args.judge_model, api_key_env=args.judge_api_key_env,
                           retries=args.retries))
    return AdvisoryJudge(provider, model=model)


def _add_provider_args(p, defaults_base_url="https://api.openai.com/v1"):
    p.add_argument("--provider", choices=["stub", "openai", "ollama"], default="stub")
    p.add_argument("--base-url", default=defaults_base_url)
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument("--api-key-env", default="OPENAI_API_KEY",
                   help="env var holding the API key (never pass a key on the CLI)")
    p.add_argument("--retries", type=int, default=2, help="retries for transient provider errors")
    p.add_argument("--plugin-module", action="append", default=[],
                   help="import a module that registers custom scorers (repeatable)")
    return p


def _add_gate_args(p):
    p.add_argument("--threshold", type=float, default=1.0, help="minimum pass rate, 0.0-1.0")
    p.add_argument("--markdown", default="", help="write Markdown report to this path")
    p.add_argument("--junit", default="", help="write JUnit XML report to this path")
    p.add_argument("--json", default="", help="write machine-readable run JSON to this path")
    p.add_argument("--record", default="", help="write a recording (case id -> output) to this path")
    p.add_argument("--prompt-version", default="")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--judge", action="store_true",
                   help="also run an advisory LLM judge (never counts toward the gate)")
    p.add_argument("--judge-provider", choices=["stub", "openai", "ollama"], default="openai")
    p.add_argument("--judge-base-url", default="https://api.openai.com/v1")
    p.add_argument("--judge-model", default="gpt-4o-mini")
    p.add_argument("--judge-api-key-env", default="OPENAI_API_KEY")
    return p


def _write_reports(args, report) -> None:
    if args.markdown:
        Path(args.markdown).write_text(render_markdown(report), encoding="utf-8")
    if args.junit:
        Path(args.junit).write_text(render_junit(report), encoding="utf-8")
    if args.json:
        save_run(report, Path(args.json))
    if args.record:
        save_recording(report, Path(args.record))


def _print_summary(args, report) -> None:
    if not args.quiet:
        print(f"{report.passed_count}/{report.total} passed "
              f"({report.pass_rate:.0%}, threshold {args.threshold:.0%})")
        for r in report.results:
            if not r.passed:
                print(f"FAIL {r.case_id}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="prompt-eval", description="Prompt & agent evaluation regression harness")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run cases and report pass/fail")
    run.add_argument("--cases", required=True)
    _add_provider_args(run)
    _add_gate_args(run)

    record = sub.add_parser("record", help="run cases and save their outputs as a recording")
    record.add_argument("--cases", required=True)
    record.add_argument("--recording", required=True, help="output recording path")
    _add_provider_args(record)
    _add_gate_args(record)

    replay = sub.add_parser("replay", help="re-score recorded outputs offline, no provider call")
    replay.add_argument("--cases", required=True)
    replay.add_argument("--recording", required=True)
    replay.add_argument("--model", default="replay")
    _add_gate_args(replay)
    replay.add_argument("--plugin-module", action="append", default=[])

    diff = sub.add_parser("diff", help="compare two run JSON files")
    diff.add_argument("--baseline", required=True)
    diff.add_argument("--new", required=True)
    diff.add_argument("--markdown", default="", help="write diff Markdown to this path")

    imp = sub.add_parser("import-promptfoo", help="convert a Promptfoo YAML file to prompt-eval YAML")
    imp.add_argument("--input", required=True)
    imp.add_argument("--output", default="", help="write to this path (default: stdout)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "diff":
            diff = diff_runs(load_run(Path(args.baseline)), load_run(Path(args.new)))
            text = render_diff_markdown(diff)
            if args.markdown:
                Path(args.markdown).write_text(text, encoding="utf-8")
            else:
                print(text)
            return 1 if diff["pass_to_fail"] else 0
        if args.command == "import-promptfoo":
            text = cases_to_yaml(import_promptfoo(Path(args.input)))
            if args.output:
                Path(args.output).write_text(text, encoding="utf-8")
            else:
                print(text)
            return 0
        _load_plugins(args)
        cases = load_cases(Path(args.cases))
        if args.command == "replay":
            if not 0.0 <= args.threshold <= 1.0:
                print("error: --threshold must be between 0.0 and 1.0", file=sys.stderr)
                return 2
            report = replay_cases(cases, load_recording(Path(args.recording)),
                                  model=args.model, prompt_version=args.prompt_version,
                                  threshold=args.threshold)
            _write_reports(args, report)
            _print_summary(args, report)
            return 0 if report.gate_passed else 1
        if not 0.0 <= args.threshold <= 1.0:
            print("error: --threshold must be between 0.0 and 1.0", file=sys.stderr)
            return 2
        provider, model = _make_provider(args)
        judge = _make_judge(args)
        report = run_cases(cases, provider, model=model,
                           prompt_version=args.prompt_version, threshold=args.threshold, judge=judge)
        if args.command == "record":
            save_recording(report, Path(args.recording))
        _write_reports(args, report)
        _print_summary(args, report)
        return 0 if report.gate_passed else 1
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
