"""Edge case and error handling tests for SlopLab CLI commands."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from sloplab.cli.main import cli


def test_cli_evaluate_nonexistent_path() -> None:
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "evaluate",
            "/tmp/non_existent_dir_12345",
            "--evaluator",
            "rules-baseline",
            "--out",
            "/tmp/out",
        ],
    )
    assert res.exit_code != 0


def test_cli_benchmark_nonexistent_suite() -> None:
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "benchmark",
            "/tmp/non_existent_suite.yaml",
            "--evaluator",
            "rules-baseline",
            "--out",
            "/tmp/out",
        ],
    )
    assert res.exit_code != 0


def test_cli_report_nonexistent_path() -> None:
    runner = CliRunner()
    res = runner.invoke(cli, ["report", "/tmp/non_existent_results_dir"])
    assert res.exit_code != 0


def test_cli_report_empty_directory(tmp_path: Path) -> None:
    runner = CliRunner()
    # Directory exists but contains no run.jsonl
    res = runner.invoke(cli, ["report", str(tmp_path)])
    assert res.exit_code != 0
    assert "does not contain a 'run.jsonl' file" in res.output
