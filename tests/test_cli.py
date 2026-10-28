import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args, cwd=None):
    env = {"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"}
    return subprocess.run(
        [sys.executable, "-m", "prompt_eval", *args],
        capture_output=True, text=True, cwd=cwd or ROOT, env=env,
    )


def test_cli_golden_passes(tmp_path):
    out = run_cli("run", "--cases", "examples/cases.yaml", "--provider", "stub",
                  "--markdown", str(tmp_path / "r.md"), "--junit", str(tmp_path / "r.xml"))
    assert out.returncode == 0, out.stdout + out.stderr
    assert "30/30 passed" in out.stdout
    assert "PASS" in (tmp_path / "r.md").read_text()
    assert "tests=\"30\"" in (tmp_path / "r.xml").read_text()


def test_cli_failing_exits_one(tmp_path):
    out = run_cli("run", "--cases", "examples/failing.yaml", "--provider", "stub")
    assert out.returncode == 1
    assert "1/3 passed" in out.stdout
    assert "FAIL fail-exact" in out.stdout


def test_cli_threshold_allows_partial(tmp_path):
    out = run_cli("run", "--cases", "examples/failing.yaml", "--provider", "stub",
                  "--threshold", "0.33")
    assert out.returncode == 0  # 1/3 = 33.3% >= 33%


def test_cli_bad_cases_file_exits_two(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("cases:\n  - id: dup\n    prompt: hi\n  - id: dup\n    prompt: hi\n")
    out = run_cli("run", "--cases", str(bad), "--provider", "stub")
    assert out.returncode == 2


def test_cli_library_entrypoint():
    # python -m prompt_eval --help must work (argparse, exit 0 via --help is 0)
    out = run_cli("--help")
    assert out.returncode == 0
    assert "prompt-eval" in out.stdout or "usage" in out.stdout.lower()


def test_golden_cases_cover_all_scorers():
    data = yaml.safe_load((ROOT / "examples" / "cases.yaml").read_text())
    assert len(data["cases"]) >= 25
    used = {e["type"] for c in data["cases"] for e in c["expected"]}
    assert used == {"exact", "regex", "json_schema", "length", "format",
                    "contains_all", "citation"}
