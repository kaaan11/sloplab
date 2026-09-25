"""Real headless UI + unchanged core: keyboard flow, lifecycle and fault cases."""

from __future__ import annotations

import asyncio
import socket
import subprocess
import threading
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("prompt_toolkit")

from prompt_toolkit.data_structures import Size
from prompt_toolkit.output import DummyOutput

from sloplab.corpus import add_report as core
from sloplab.corpus.loader import CanonicalFixture, DerivedFixture, discover_fixtures
from sloplab.corpus.validation import ValidationResult, validate_corpus
from sloplab.models.enums import DIMENSIONS, ReportClass
from sloplab.models.manifest import CanonicalManifest
from sloplab.tui.app import Step
from tests._add_report_helpers import make_corpus, make_source, snapshot
from tests._tui_helpers import inject_cleanup, running, until

F6, F7, F8 = "\x1b[17~", "\x1b[18~", "\x1b[19~"


def test_keyboard_only_happy_path(tmp_path: Path) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)
    before = snapshot(root)

    async def scenario() -> None:
        async with running(source.path, root) as driver:
            ui = driver.ui
            assert ui.source == source
            assert source.title in ui.source_description()
            # No focus(), setters, next() or create() calls: every annotation
            # and transition is driven by real terminal input bytes.
            await driver.keys("keyboard-001" + F7)
            assert int(ui.step) == int(Step.GROUND_TRUTH)
            await driver.keys("\x1b[A\x1b[A \t\x1b[B \t" + "\x1b[B" * 4 + " \t")
            await driver.keys("Synthetic test\tSynthetic only" + F7)
            assert ui.classes.current_value == ReportClass.VALID
            assert ui.reproducible.current_value == "yes"
            assert ui.impact.current_value == "medium"
            assert ui.rationale.text == "Synthetic test"
            assert ui.note.text == "Synthetic only"
            assert int(ui.step) == int(Step.EVIDENCE)
            assert ui.evidence.current_values == ["reproduction_steps"]
            await driver.keys(F7)
            for _ in DIMENSIONS:
                await driver.keys("\x01\x0b0.912345\t")
            await driver.keys(F7)
            assert ui.can_create
            assert ui.session.prepared is not None
            assert ui.session.prepared.fixture_validation.render() in ui.review.text
            assert ui.session.prepared.preflight.render() in ui.review.text
            assert ui.session.prepared.manifest_text in ui.review.text
            assert not ui.confirm.checked
            await driver.keys(F8)
            assert not (root / "canonical/keyboard-001").exists()
            await driver.keys(" " + F8)
            assert int(ui.step) == int(Step.SUCCESS), ui.message
            result = ui.session.result
            assert result is not None and result.committed
            manifest = CanonicalManifest.model_validate(
                __import__("yaml").safe_load(result.manifest_path.read_text())
            )
            assert manifest.ground_truth.expected_dimensions == dict.fromkeys(DIMENSIONS, 0.912345)
            assert "1 -> 2" in ui.success.text
            assert "0  warnings: 0" in ui.success.text
            assert source.path.read_bytes() == result.report_path.read_bytes() == source.content
            assert all(snapshot(root)[key] == value for key, value in before.items())
            canonical, derived = discover_fixtures(root)
            assert validate_corpus(canonical, derived, root).ok
            await driver.keys("\x11")
            assert await driver.task is result
        assert not list(tmp_path.glob(".sloplab-stage-*"))

    asyncio.run(scenario())


@pytest.mark.parametrize("slug", ["../escape", "UpperCase", "", "existing"])
def test_source_slug_collision(tmp_path: Path, slug: str) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)
    before = snapshot(root)

    async def scenario() -> None:
        async with running(source.path, root) as driver:
            driver.ui.slug_input.text = slug
            driver.ui.next()
            await driver.idle()
            assert int(driver.ui.step) == int(Step.SOURCE)
            assert driver.ui.message
            assert not driver.ui.can_create
        assert snapshot(root) == before

    asyncio.run(scenario())


@pytest.mark.parametrize("text", ["No H1", "```\n# fake H1\n```"])
def test_missing_h1(tmp_path: Path, text: str) -> None:
    path = tmp_path / "input.md"
    path.write_text(text)
    root = make_corpus(tmp_path)

    async def scenario() -> None:
        async with running(path, root) as driver:
            assert driver.ui.source is None
            assert "no H1" in driver.ui.message
            assert not driver.ui.can_create

    asyncio.run(scenario())


@pytest.mark.parametrize("value", ["-0.1", "1.1", "nan", "inf", "", "words"])
def test_invalid_dimension_keeps_form(tmp_path: Path, value: str) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)
    before = snapshot(root)

    async def scenario() -> None:
        async with running(source.path, root) as driver:
            await driver.review()
            driver.ui.back()
            await driver.idle()
            driver.ui.dimensions[DIMENSIONS[0]].text = value
            driver.ui.next()
            assert int(driver.ui.step) == int(Step.DIMENSIONS)
            assert driver.ui.message
            assert driver.ui.session.prepared is None
        assert snapshot(root) == before

    asyncio.run(scenario())


def test_back_edit_cancel_closes_stage(tmp_path: Path) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)
    before = snapshot(root)

    async def scenario() -> None:
        async with running(source.path, root) as driver:
            await driver.review()
            prepared = driver.ui.session.prepared
            assert prepared is not None
            stage = prepared.staged_directory.parents[1]
            driver.ui.confirm.checked = True
            await driver.keys(F6)
            assert not stage.exists()
            assert not driver.ui.can_create
            assert not driver.ui.confirm.checked
            driver.ui.dimensions[DIMENSIONS[0]].text = "0.123456789"
            await driver.keys(F7)
            assert driver.ui.session.prepared is not None
            assert "0.123456789" in driver.ui.review.text
            await driver.keys("\x03")
            assert await driver.task is None
        assert snapshot(root) == before
        assert not list(tmp_path.glob(".sloplab-stage-*"))

    asyncio.run(scenario())


def test_evidence_detection_is_structural_and_required_selection_fails(tmp_path: Path) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)

    async def scenario() -> None:
        async with running(source.path, root) as driver:
            ui = driver.ui
            ui.slug_input.text = "new-001"
            ui.next()
            await driver.idle()
            ui.next()
            assert "reproduction steps: heading found" in ui.evidence_description()
            assert "expected security boundary: heading not found" in ui.evidence_description()
            ui.evidence.current_values = ["expected_security_boundary"]
            ui.next()
            ui.next()
            await driver.idle()
            assert ui.session.prepared is None
            assert "required evidence section missing" in ui.review.text
            assert not ui.can_create

    asyncio.run(scenario())


@pytest.mark.parametrize("report_class", list(ReportClass))
def test_class_selection_and_warning_are_core_results(
    tmp_path: Path, report_class: ReportClass
) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)

    async def scenario() -> None:
        async with running(source.path, root) as driver:
            driver.ui.classes.current_value = report_class
            await driver.review()
            prepared = driver.ui.session.prepared
            assert prepared is not None
            assert prepared.manifest.report_class == report_class
            assert prepared.manifest.expected_decision().value in driver.ui.review.text
            if report_class == ReportClass.VALID:
                assert prepared.preflight.warnings
                assert prepared.preflight.warnings[0].message in driver.ui.review.text

    asyncio.run(scenario())


@pytest.mark.parametrize("target", ["lock", "stage", "both"])
@pytest.mark.parametrize("error_type", [OSError, KeyboardInterrupt])
@pytest.mark.parametrize("remove_first", [False, True])
def test_ui_cleanup_fault_is_committed_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    error_type: type[BaseException],
    remove_first: bool,
) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)
    before = snapshot(root)

    async def scenario() -> None:
        async with running(source.path, root) as driver:
            await driver.review()
            prepared = driver.ui.session.prepared
            assert prepared is not None
            paths = inject_cleanup(monkeypatch, target, error_type, remove_first=remove_first)
            driver.ui.confirm.checked = True
            driver.ui.create()
            await driver.idle()
            result = driver.ui.session.result
            assert result is not None and result is prepared.commit_result
            assert driver.ui.session.prepared is None
            assert int(driver.ui.step) == int(Step.SUCCESS)
            assert "Fixture added" in driver.ui.success.text
            assert "Cleanup incomplete" in driver.ui.success.text
            assert "Do not retry add-report" in driver.ui.success.text
            assert "Cannot create" not in driver.ui.success.text
            assert driver.ui.message == ""
            assert len(paths) == (2 if target == "both" else 1)
            assert all(str(path) in driver.ui.success.text for path in paths)
            assert all(path.exists() is not remove_first for path in paths)
            assert all(snapshot(root)[key] == value for key, value in before.items())
            assert result.report_path.read_bytes() == source.path.read_bytes() == source.content

    asyncio.run(scenario())


@pytest.mark.parametrize("change", ["source", "corpus", "stage"])
def test_stale_review_fails_without_creation(tmp_path: Path, change: str) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)

    async def scenario() -> None:
        async with running(source.path, root) as driver:
            await driver.review()
            prepared = driver.ui.session.prepared
            assert prepared is not None
            if change == "source":
                source.path.write_text("# Externally changed report")
            elif change == "corpus":
                (root / "sentinel.txt").write_text("external data")
            else:
                (prepared.staged_directory / "report.md").write_text("# Modified stage")
            driver.ui.confirm.checked = True
            driver.ui.create()
            await driver.idle()
            assert int(driver.ui.step) == int(Step.REVIEW)
            assert driver.ui.session.result is None
            assert not driver.ui.can_create
            assert "changed" in driver.ui.review.text
            assert not prepared.destination.exists()

    asyncio.run(scenario())


def test_postwrite_failure_rolls_back_in_ui(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)
    before = snapshot(root)

    def fail_postwrite(
        canonical: list[CanonicalFixture],
        derived: list[DerivedFixture],
        corpus_root: Path | None = None,
    ) -> ValidationResult:
        result = validate_corpus(canonical, derived, corpus_root)
        if (root / "canonical/new-001").exists():
            result.error("injected", "postwrite rejected")
        return result

    async def scenario() -> None:
        async with running(source.path, root) as driver:
            await driver.review()
            monkeypatch.setattr(core, "validate_corpus", fail_postwrite)
            driver.ui.confirm.checked = True
            driver.ui.create()
            await driver.idle()
            assert "postwrite rejected" in driver.ui.review.text
            assert not driver.ui.can_create
            assert driver.ui.session.result is None
            assert snapshot(root) == before

    asyncio.run(scenario())


@pytest.mark.parametrize("exit_kind", ["key", "eof", "task_cancel"])
def test_commit_not_abandoned_and_loop_responsive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_kind: str
) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = core.commit_add_report
    thread_ids: list[int] = []

    def blocked(prepared: core.PreparedReport, *, confirmed: bool = False) -> core.AddReportResult:
        thread_ids.append(threading.get_ident())
        entered.set()
        assert release.wait(5), "test must release the commit worker"
        return original(prepared, confirmed=confirmed)

    async def scenario() -> None:
        async with running(source.path, root) as driver:
            await driver.review()
            monkeypatch.setattr(core, "commit_add_report", blocked)
            driver.ui.confirm.checked = True
            driver.ui.create()
            try:
                await until(entered.is_set)
                assert thread_ids[0] != threading.get_ident()
                if exit_kind == "key":
                    driver.pipe.send_text("\x03")
                    await asyncio.sleep(0.1)
                    assert "Operation in progress" in driver.ui.message
                elif exit_kind == "eof":
                    driver.pipe.close()
                else:
                    driver.task.cancel()
                await asyncio.sleep(0.05)
                assert not driver.task.done()
            finally:
                release.set()
            await driver.idle()
            assert driver.ui.session.result is not None
            assert driver.ui.session.result.committed
            if exit_kind == "key":
                assert int(driver.ui.step) == int(Step.SUCCESS)
                driver.ui.cancel()
            assert await driver.task is driver.ui.session.result
        assert not list(tmp_path.glob(".sloplab-stage-*"))

    asyncio.run(scenario())


def test_shutdown_closes_uncommitted_review(tmp_path: Path) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)
    before = snapshot(root)

    async def scenario() -> None:
        async with running(source.path, root) as driver:
            await driver.review()
            driver.pipe.close()
            assert await driver.task is None
        assert not list(tmp_path.glob(".sloplab-stage-*"))
        assert snapshot(root) == before

    asyncio.run(scenario())


def test_offline_no_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("No network or subprocess allowed in builder")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)

    async def scenario() -> None:
        async with running(source.path, root) as driver:
            await driver.review()
            driver.ui.confirm.checked = True
            driver.ui.create()
            await driver.idle()
            assert driver.ui.session.result is not None

    asyncio.run(scenario())


def test_narrow_terminal_blocks_continue(tmp_path: Path) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)

    class Narrow(DummyOutput):
        def get_size(self) -> Size:
            return Size(rows=15, columns=40)

    async def scenario() -> None:
        async with running(source.path, root, output=Narrow()) as driver:
            driver.ui.slug_input.text = "new-001"
            driver.ui.next()
            assert int(driver.ui.step) == int(Step.SOURCE)
            assert "70 x 20" in driver.ui.message

    asyncio.run(scenario())


@pytest.mark.parametrize("error_type", [OSError, KeyboardInterrupt])
def test_cancel_cleanup_failure_is_not_false_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: type[BaseException]
) -> None:
    source, root = make_source(tmp_path), make_corpus(tmp_path)
    before = snapshot(root)

    async def scenario() -> None:
        async with running(source.path, root) as driver:
            await driver.review()
            inject_cleanup(monkeypatch, "stage", error_type)
            driver.ui.cancel()
            await driver.idle()
            assert driver.ui.session.result is None
            assert "cleanup incomplete" in driver.ui.message
            assert not driver.task.done()
            assert "Fixture added" not in driver.ui.success.text
        assert snapshot(root) == before

    asyncio.run(scenario())


def test_renderer_callback_failure_still_closes_prepared_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sloplab.tui.app import ReportBuilder

    source, root = make_source(tmp_path), make_corpus(tmp_path)
    before = snapshot(root)

    def fail_render(self: ReportBuilder, _: core.PreparedReport) -> None:
        # Return from the worker succeeded; only the view callback is broken.
        self.application.exit()
        raise RuntimeError("injected review rendering")

    monkeypatch.setattr(ReportBuilder, "_prepared", fail_render)

    async def scenario() -> None:
        with pytest.raises(core.AddReportError, match="injected review rendering"):
            async with running(source.path, root) as driver:
                ui = driver.ui
                ui.slug_input.text = "new-001"
                ui.next()
                await driver.idle()
                ui.next()
                ui.next()
                ui.next()
                await driver.task
        assert snapshot(root) == before
        assert not list(tmp_path.glob(".sloplab-stage-*"))

    asyncio.run(scenario())
