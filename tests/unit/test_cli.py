"""Tests for the CLI entry point."""

from click.testing import CliRunner

from sloplab import __version__
from sloplab.cli.main import cli


def test_cli_version() -> None:
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_help_lists_commands() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    for command in (
        "validate",
        "mutate",
        "materialize",
        "evaluate",
        "benchmark",
        "compare",
        "report",
    ):
        assert command in result.output


def test_validate_requires_existing_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = CliRunner().invoke(cli, ["validate", str(tmp_path / "missing")])
    assert result.exit_code != 0


def test_mutate_supports_kebab_case_and_errors(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from pathlib import Path

    fixture = Path(__file__).resolve().parents[2] / "corpus/canonical/authz-001"
    runner = CliRunner()

    # Kebab-case operator must succeed
    res = runner.invoke(cli, ["mutate", str(fixture), "--operator", "remove-reproduction-step"])
    assert res.exit_code == 0
    assert "# operator: remove-reproduction-step" in res.output

    # Unknown operator must give a clean ClickException without unhandled traceback
    res_err = runner.invoke(cli, ["mutate", str(fixture), "--operator", "non_existent_op"])
    assert res_err.exit_code != 0
    assert "Error: unknown mutation operator" in res_err.output


def test_compare_with_direct_metrics_json_files(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    runner = CliRunner()
    m1 = tmp_path / "metrics-m1.json"
    m2 = tmp_path / "metrics-m2.json"
    data = {
        "evaluator_name": "test-eval",
        "decision_accuracy": 0.85,
        "mutation_detection_rate": 0.75,
        "false_reassurance_rate": 0.1,
        "over_rejection_rate": 0.0,
        "robustness_delta": 0.05,
        "presentation_susceptibility": 0.0,
        "calibration_error": 0.15,
        "aux_robustness_score": 0.8,
    }
    m1.write_text(json.dumps(data), encoding="utf-8")
    m2.write_text(json.dumps(data), encoding="utf-8")

    res = runner.invoke(cli, ["compare", str(m1), str(m2)])
    assert res.exit_code == 0
    assert "test-eval" in res.output
