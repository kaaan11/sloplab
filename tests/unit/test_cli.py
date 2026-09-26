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


def test_compare_keeps_same_basename_directories_separate(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    runner = CliRunner()
    roots = [tmp_path / "a" / "results", tmp_path / "b" / "results"]
    for root, accuracy in zip(roots, (0.1, 0.9), strict=True):
        root.mkdir(parents=True)
        (root / "run.jsonl").write_text("", encoding="utf-8")
        (root / "metrics-rules-baseline.json").write_text(
            json.dumps(
                {
                    "evaluator_name": "rules-baseline",
                    "decision_accuracy": accuracy,
                }
            ),
            encoding="utf-8",
        )

    result = runner.invoke(cli, ["compare", str(roots[0]), str(roots[1])])

    assert result.exit_code == 0, result.output
    assert "0.100" in result.output
    assert "0.900" in result.output
    assert result.output.count("rules-baseline") >= 2


def test_compare_rejects_duplicate_input_directory(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    root = tmp_path / "results"
    root.mkdir()
    (root / "run.jsonl").write_text("", encoding="utf-8")
    (root / "metrics-rules-baseline.json").write_text(
        json.dumps({"evaluator_name": "rules-baseline", "decision_accuracy": 0.5}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["compare", str(root), str(root)])

    assert result.exit_code != 0
    assert "duplicate compare input" in result.output
