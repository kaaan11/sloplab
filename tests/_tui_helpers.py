"""Headless keyboard driver and fault injection for the optional Report Builder."""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from prompt_toolkit.input import PipeInput
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from sloplab.corpus.add_report import AddReportResult
from sloplab.tui.app import ReportBuilder, Step


async def until(predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0.005)


@dataclass
class Driver:
    ui: ReportBuilder
    pipe: PipeInput
    task: asyncio.Task[AddReportResult | None]

    async def idle(self) -> None:
        await until(lambda: self.ui.task is not None and self.ui.task.done())
        assert self.ui.task is not None
        self.ui.task.result()
        await asyncio.sleep(0.01)

    async def keys(self, text: str) -> None:
        self.pipe.send_text(text)
        await asyncio.sleep(0.06)
        if self.ui.busy:
            await self.idle()

    async def review(self, slug: str = "new-001") -> None:
        self.ui.slug_input.text = slug
        self.ui.next()
        await self.idle()
        assert int(self.ui.step) == int(Step.GROUND_TRUTH), self.ui.message
        self.ui.next()
        self.ui.next()
        self.ui.next()
        await self.idle()
        assert int(self.ui.step) == int(Step.REVIEW), self.ui.message


@asynccontextmanager
async def running(
    report: Path, corpus: Path, *, output: DummyOutput | None = None
) -> AsyncIterator[Driver]:
    with create_pipe_input() as pipe:
        ui = ReportBuilder(report, corpus, input=pipe, output=output or DummyOutput())
        task = asyncio.create_task(ui.run_async())
        driver = Driver(ui, pipe, task)
        try:
            await driver.idle()
            yield driver
        finally:
            if not task.done():
                if ui.busy:
                    await driver.idle()
                ui.cancel()
            await asyncio.wait_for(task, 5)


def inject_cleanup(
    monkeypatch: Any, target: str, error_type: type[BaseException], *, remove_first: bool = False
) -> list[Path]:
    paths: list[Path] = []
    original_rmdir = Path.rmdir
    original_rmtree = cast(Any, tempfile.TemporaryDirectory)._rmtree

    def rmdir(path: Path) -> None:
        if target in ("lock", "both") and path.name.endswith(".sloplab-add-report.lock"):
            paths.append(path)
            if remove_first:
                original_rmdir(path)
            raise error_type("injected lock cleanup")
        original_rmdir(path)

    def rmtree(
        cls: type[tempfile.TemporaryDirectory[str]], path: str, *args: Any, **kwargs: Any
    ) -> None:
        if target in ("stage", "both") and Path(path).name.startswith(".sloplab-stage-"):
            paths.append(Path(path))
            if remove_first:
                original_rmtree(path, *args, **kwargs)
            raise error_type("injected stage cleanup")
        original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(Path, "rmdir", rmdir)
    monkeypatch.setattr(tempfile.TemporaryDirectory, "_rmtree", classmethod(rmtree))
    return paths
