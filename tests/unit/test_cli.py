"""Tests for the CLI entry point."""

import pytest
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
    assert r"results-\xff" in result.output
    assert "\udcff" not in result.output


def test_compare_preserves_distinct_long_evaluator_labels(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    root = tmp_path / "results"
    root.mkdir()
    (root / "run.jsonl").write_text("", encoding="utf-8")
    # Names share a 28-char prefix so base's `n[:28]` header truncation
    # renders them identically; the fix must preserve the full labels.
    names = ("a" * 28 + "-A", "a" * 28 + "-B")
    for name, accuracy in zip(names, (0.1, 0.9), strict=True):
        (root / f"metrics-{name}.json").write_text(
            json.dumps({"evaluator_name": name, "decision_accuracy": accuracy}),
            encoding="utf-8",
        )

    result = CliRunner().invoke(cli, ["compare", str(root)])

    assert result.exit_code == 0, result.output
    assert names[0] in result.output
    assert names[1] in result.output
    assert "0.100" in result.output
    assert "0.900" in result.output


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


def test_portable_path_str_falls_back_to_absolute_on_cross_drive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F3 (#60): os.path.relpath ValueError (Windows cross-drive) keeps absolute."""
    from pathlib import Path
    from typing import Any

    from sloplab.cli.main import _portable_path_str

    def _cross_drive(*_args: Any, **_kwargs: Any) -> str:
        raise ValueError("path is on mount 'C:', start on mount 'D:'")

    monkeypatch.setattr("os.path.relpath", _cross_drive)
    assert _portable_path_str(Path("/repo/out/suite-index.jsonl")) == "/repo/out/suite-index.jsonl"
