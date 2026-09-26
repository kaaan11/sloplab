"""Tests for the CLI entry point."""

from click.testing import CliRunner
import pytest

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
    import hashlib
    import json
    import os

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
    token_a = hashlib.sha256(os.fsencode(roots[0].resolve())).hexdigest()[:8]
    token_b = hashlib.sha256(os.fsencode(roots[1].resolve())).hexdigest()[:8]
    assert token_a in result.output
    assert token_b in result.output
    assert token_a != token_b


def test_compare_hashes_non_utf8_posix_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json
    import os

    if os.name == "nt":
        pytest.skip("surrogate-escaped POSIX filenames are not available on Windows")

    root = tmp_path / os.fsdecode(b"results-\xff")
    root.mkdir()
    (root / "run.jsonl").write_text("", encoding="utf-8")
    (root / "metrics-rules-baseline.json").write_text(
        json.dumps({"evaluator_name": "rules-baseline", "decision_accuracy": 0.5}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["compare", str(root)])

    assert result.exit_code == 0, result.output
    expected = __import__("hashlib").sha256(os.fsencode(root.resolve())).hexdigest()[:8]
    assert expected in result.output


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
