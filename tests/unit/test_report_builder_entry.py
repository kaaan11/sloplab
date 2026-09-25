"""Optional-entry and presentation contract checks, including fresh base imports."""

from __future__ import annotations

import asyncio
import builtins
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.corpus import add_report as core
from sloplab.corpus.conventions import EVIDENCE_SECTION_PATTERNS
from sloplab.models.enums import DIMENSIONS, ReportClass
from sloplab.tui.presentation import display_text, error_text
from tests._add_report_helpers import answers, make_corpus, make_source


def test_missing_optional_dependency_is_actionable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = builtins.__import__

    def missing(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "sloplab.tui.app":
            raise ModuleNotFoundError("No module named 'prompt_toolkit'", name="prompt_toolkit")
        return original(name, *args, **kwargs)

    source, root = make_source(tmp_path), make_corpus(tmp_path)
    monkeypatch.setattr(builtins, "__import__", missing)
    result = CliRunner().invoke(
        cli, ["add-report", str(source.path), "--corpus", str(root), "--ui"]
    )
    assert result.exit_code != 0
    assert 'pip install "sloplab[ui]"' in result.output
    assert "uv sync --extra ui" in result.output
    assert "Traceback" not in result.output
    assert not (root / "canonical/new-001").exists()


def test_base_cli_does_not_import_optional_ui() -> None:
    # A fresh interpreter avoids a test's already-cached optional imports.
    code = """
import sys
from sloplab.cli.main import cli
from click.testing import CliRunner
for args in (("--help",), ("add-report", "--help"), ("validate", "corpus/")):
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
assert not any(n.startswith(("prompt_toolkit", "sloplab.tui")) for n in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_ui_option_dispatches_only_to_ui(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from sloplab.cli import add_report as classic
    from sloplab.tui import launch

    calls: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        launch, "run_report_builder", lambda report, corpus: calls.append((report, corpus))
    )
    monkeypatch.setattr(classic, "run_add_report", lambda *_: pytest.fail("UI called Click wizard"))
    source, root = make_source(tmp_path), make_corpus(tmp_path)
    result = CliRunner().invoke(
        cli, ["add-report", str(source.path), "--corpus", str(root), "--ui"]
    )
    assert result.exit_code == 0, result.output
    assert calls == [(source.path, root)]


def test_cli_ui_same_annotations_same_manifest(tmp_path: Path) -> None:
    pytest.importorskip("prompt_toolkit")
    from tests._tui_helpers import running

    source = make_source(tmp_path)
    first, second = tmp_path / "cli", tmp_path / "tui"
    first.mkdir()
    second.mkdir()
    cli_root, tui_root = make_corpus(first), make_corpus(second)
    result = CliRunner().invoke(
        cli, ["add-report", str(source.path), "--corpus", str(cli_root)], input=answers()
    )
    assert result.exit_code == 0, result.output

    async def scenario() -> None:
        async with running(source.path, tui_root) as driver:
            ui = driver.ui
            ui.classes.current_value = ReportClass.VALID
            ui.reproducible.current_value = "yes"
            ui.impact.current_value = "medium"
            ui.rationale.text = "Synthetic test"
            ui.note.text = "Synthetic only"
            ui.evidence.current_values = [
                key for key in EVIDENCE_SECTION_PATTERNS if key == "reproduction_steps"
            ]
            for name in DIMENSIONS:
                ui.dimensions[name].text = "0.9"
            await driver.review()
            ui.confirm.checked = True
            ui.create()
            await driver.idle()
            assert ui.session.result is not None

    asyncio.run(scenario())
    # Byte identity is stronger than only comparing parsed ground truth.
    assert (cli_root / "canonical/new-001/manifest.yaml").read_bytes() == (
        tui_root / "canonical/new-001/manifest.yaml"
    ).read_bytes()
    assert (cli_root / "canonical/new-001/report.md").read_bytes() == (
        tui_root / "canonical/new-001/report.md"
    ).read_bytes()


def test_display_sanitizes_controls_without_changing_core_input() -> None:
    raw = "title\x1b[31m\r\x07\u202e[red]literal[/red]\nnext"
    shown = display_text(raw)
    assert (
        "\x1b" not in shown and "\r" not in shown and "\x07" not in shown and "\u202e" not in shown
    )
    assert "[red]literal[/red]" in shown
    assert "\nnext" in shown
    error = core.AddReportError("primary")
    error.add_note("cleanup path")
    assert error_text(error) == "primary\ncleanup path"
