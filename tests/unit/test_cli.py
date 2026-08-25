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
