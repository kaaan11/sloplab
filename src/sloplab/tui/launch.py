"""Lazy optional UI entry point; ordinary CLI imports no prompt_toolkit modules."""

from __future__ import annotations

import asyncio
from pathlib import Path

from sloplab.corpus.add_report import AddReportError
from sloplab.tui.presentation import error_text, success_text


def run_report_builder(report: Path, corpus: Path) -> None:
    try:
        from sloplab.tui.app import ReportBuilder
    except ModuleNotFoundError as error:
        if error.name in ("prompt_toolkit", "wcwidth") or (error.name or "").startswith(
            "prompt_toolkit."
        ):
            raise AddReportError(
                'SlopLab TUI support is not installed. Install with: pip install "sloplab[ui]" '
                "(repository checkout: uv sync --extra ui)."
            ) from error
        raise
    try:
        app = ReportBuilder(report, corpus)
        result = asyncio.run(app.run_async())
    except AddReportError:
        raise
    except Exception as error:
        raise AddReportError("Report Builder error: " + error_text(error)) from error
    # The alternate screen is gone. Keep an actionable, copyable final result in
    # terminal scrollback too, including warnings added during context shutdown.
    print(success_text(result) if result is not None else "Cancelled; no fixture was created.")
    if app.exit_notice:
        print(error_text(AddReportError(app.exit_notice)))
