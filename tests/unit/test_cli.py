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


def test_report_supports_directory_and_run_jsonl(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    from sloplab.reporting.writers import default_run_metadata

    runner = CliRunner()
    run_file = tmp_path / "run.jsonl"
    meta_line = default_run_metadata(suite_name="test-suite").model_dump_json()
    case_line = json.dumps(
        {
            "record_type": "case",
            "case_id": "c1",
            "case_kind": "canonical",
            "evaluator_name": "mock-eval",
            "evaluator_version": "1.0",
            "decision": "accept",
            "expected_decision": "accept",
            "confidence": 0.9,
            "dimensions": {
                "reproducibility": 1.0,
                "evidence_completeness": 1.0,
                "claim_evidence_consistency": 1.0,
                "impact_calibration": 1.0,
                "scope_consistency": 1.0,
            },
            "correct": True,
            "findings": [],
            "rationale": "ok",
            "report_class": "valid",
        }
    )
    run_file.write_text(f"{meta_line}\n{case_line}\n", encoding="utf-8")

    # Call with directory
    res_dir = runner.invoke(cli, ["report", str(tmp_path)])
    assert res_dir.exit_code == 0
    assert "SlopLab results (test-suite)" in res_dir.output

    # Call with direct file
    res_file = runner.invoke(cli, ["report", str(run_file)])
    assert res_file.exit_code == 0
    assert "SlopLab results (test-suite)" in res_file.output
