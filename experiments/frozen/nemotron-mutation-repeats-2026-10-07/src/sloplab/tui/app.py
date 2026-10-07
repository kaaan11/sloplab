"""Keyboard-first Report Builder; optional prompt_toolkit presentation only."""

from __future__ import annotations

import asyncio
import math
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import IntEnum
from functools import partial
from pathlib import Path
from typing import Any

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import (
    ConditionalContainer,
    DynamicContainer,
    HSplit,
    Layout,
    ScrollablePane,
    VSplit,
    Window,
)
from prompt_toolkit.layout.containers import AnyContainer, Container
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.output import ColorDepth, Output
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Button, Checkbox, CheckboxList, Frame, Label, RadioList, TextArea
from pydantic import ValidationError

from sloplab.corpus import add_report as core
from sloplab.corpus.conventions import EVIDENCE_SECTION_PATTERNS
from sloplab.models.enums import DIMENSIONS, ImpactClass, ReportClass, canonical_expected_decision
from sloplab.models.manifest import CanonicalManifest, GroundTruth
from sloplab.tui.presentation import (
    CLASS_COPY,
    DIMENSION_COPY,
    display_text,
    error_text,
    review_text,
    success_text,
)
from sloplab.tui.session import BuilderSession, SourcePreview


class Step(IntEnum):
    SOURCE = 0
    GROUND_TRUTH = 1
    EVIDENCE = 2
    DIMENSIONS = 3
    REVIEW = 4
    SUCCESS = 5


STEP_NAMES = ("Source", "Ground truth", "Evidence", "Dimensions", "Review", "Success")
STYLE = Style.from_dict(
    {
        "": "bg:#0d1117 #e6edf3",
        "header": "bg:#161b22 #79c0ff bold",
        "frame.border": "#30363d",
        "frame.label": "#79c0ff bold",
        "text-area": "bg:#161b22 #e6edf3",
        "text-area focused": "bg:#21262d #ffffff",
        "button": "bg:#21262d #c9d1d9",
        "button.focused": "bg:#1f6feb #ffffff bold",
        "radio-selected": "bg:#1f6feb #ffffff bold",
        "checkbox-selected": "bg:#1f6feb #ffffff bold",
        "status": "#ffdf5d",
        "help": "#8b949e",
    }
)


@dataclass(frozen=True)
class Outcome:
    """Transport BaseException as data so a worker interrupt can't kill the UI loop."""

    value: Any = None
    error: BaseException | None = None


def capture(operation: Callable[[], Any]) -> Outcome:
    try:
        return Outcome(value=operation())
    except BaseException as error:
        return Outcome(error=error)


async def settle(task: asyncio.Future[Any]) -> Any:
    """Drain an owned operation even if its awaiting UI task is cancelled.

    Never cancel the executor future: cancellation cannot stop a filesystem
    transaction thread. Only use for finite operations during builder shutdown.
    """
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


class ReportBuilder:
    """Own UI state and exactly one serialized, non-abandoned I/O worker."""

    def __init__(
        self,
        report: Path,
        corpus: Path,
        *,
        input: Input | None = None,
        output: Output | None = None,
    ) -> None:
        self.session = BuilderSession(corpus)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sloplab-builder")
        self.task: asyncio.Task[None] | None = None
        self.busy = False
        self.closing = False
        self.step = Step.SOURCE
        self.source: core.ReportSource | None = None
        self.preview: SourcePreview | None = None
        self.message = ""
        self.operation_label = ""
        self.exit_notice = ""
        self.path_input = TextArea(text=str(report), multiline=False, height=1)
        self.slug_input = TextArea(multiline=False, height=1)
        self.classes = RadioList(
            [(item, CLASS_COPY[item]) for item in ReportClass], default=ReportClass.REVIEW
        )
        self.reproducible = RadioList(
            [("unknown", "Unknown"), ("yes", "Yes"), ("no", "No")], default="unknown"
        )
        self.impact = RadioList(
            [("unknown", "Unknown (not annotated)")]
            + [(item.value, item.value.title()) for item in ImpactClass],
            default="unknown",
        )
        self.rationale = TextArea(height=3)
        self.note = TextArea(height=3)
        self.claims = TextArea(height=3)
        self.evidence = CheckboxList(
            [(key, key.replace("_", " ")) for key in EVIDENCE_SECTION_PATTERNS]
        )
        self.dimensions = {
            key: TextArea(text="0.5", multiline=False, height=1) for key in DIMENSIONS
        }
        self.confirm = Checkbox("I confirm this report is synthetic and authorize creation.")
        self.review = TextArea(read_only=True, scrollbar=True)
        self.success = TextArea(read_only=True, scrollbar=True)
        self.messages = TextArea(read_only=True, height=3, scrollbar=True, style="class:status")
        self.waiting = TextArea(read_only=True)
        self.next_button = Button("Continue >", handler=self.next, width=16)
        self.back_button = Button("< Back", handler=self.back, width=12)
        self.create_button = Button("Create fixture", handler=self.create, width=20)
        self.cancel_button = Button("Cancel", handler=self.cancel, width=12)
        self.done_button = Button("Done", handler=self.cancel, width=12)
        self.forms = self._forms()
        self.focus_targets: list[AnyContainer] = [
            self.path_input,
            self.classes,
            self.evidence,
            self.dimensions[DIMENSIONS[0]],
            self.review,
            self.success,
        ]
        body = DynamicContainer(lambda: self.waiting if self.busy else self.forms[self.step])
        navigation = VSplit(
            [
                ConditionalContainer(
                    self.back_button,
                    Condition(lambda: 0 < self.step < Step.SUCCESS and not self.busy),
                ),
                ConditionalContainer(
                    self.next_button, Condition(lambda: self.step < Step.REVIEW and not self.busy)
                ),
                ConditionalContainer(self.create_button, Condition(lambda: self.can_create)),
                ConditionalContainer(
                    self.cancel_button, Condition(lambda: self.step != Step.SUCCESS)
                ),
                ConditionalContainer(
                    self.done_button, Condition(lambda: self.step == Step.SUCCESS)
                ),
            ],
            padding=2,
            height=1,
        )
        root = HSplit(
            [
                Window(
                    FormattedTextControl(
                        " SLOPLAB  /  Report Builder\n Local, offline synthetic corpus authoring"
                    ),
                    height=2,
                    style="class:header",
                ),
                Window(FormattedTextControl(self.stepper), height=1),
                ConditionalContainer(
                    Label("[!] Enlarge terminal to at least 70 x 20. Ctrl-Q cancels."),
                    Condition(lambda: not self.usable_size),
                ),
                Frame(body, title=lambda: STEP_NAMES[self.step]),
                ConditionalContainer(self.messages, Condition(lambda: bool(self.message))),
                navigation,
                Window(
                    FormattedTextControl(
                        " Tab / Shift-Tab: focus   Arrows / Space: select\n"
                        " F6: back   F7: next   F8: create   Ctrl-Q / Ctrl-C: cancel"
                    ),
                    height=2,
                    style="class:help",
                ),
            ]
        )
        self.application: Application[None] = Application(
            layout=Layout(root, focused_element=self.path_input),
            key_bindings=self._bindings(),
            full_screen=True,
            style=STYLE,
            color_depth=ColorDepth.DEPTH_1_BIT if "NO_COLOR" in os.environ else None,
            mouse_support=False,
            input=input,
            output=output,
        )

    @property
    def usable_size(self) -> bool:
        if not hasattr(self, "application"):
            return True
        size = self.application.output.get_size()
        return size.columns >= 70 and size.rows >= 20

    @property
    def can_create(self) -> bool:
        return self.step == Step.REVIEW and not self.busy and self.session.prepared is not None

    def stepper(self) -> str:
        return "  " + " > ".join(
            ("[" + name + "]") if i == self.step else name
            for i, name in enumerate(("Source", "Truth", "Evidence", "Scores", "Review", "Done"))
        )

    def _forms(self) -> list[Container]:
        def field(title: str, widget: AnyContainer) -> Frame:
            return Frame(widget, title=title)

        def meter(key: str) -> str:
            # Visual approximation only; the untouched numeric field is what is
            # parsed and validated by GroundTruth. Never round the stored value.
            raw = self.dimensions[key].text
            try:
                value = float(raw)
                filled = round(min(1.0, max(0.0, value)) * 20) if math.isfinite(value) else 0
            except ValueError:
                filled = 0
            return "[" + "=" * filled + "." * (20 - filled) + "]  " + display_text(raw)

        scores: list[AnyContainer] = [
            Label(
                "Human-authored targets, not model predictions. "
                "Enter finite values from 0.0 to 1.0."
            )
        ]
        for key in DIMENSIONS:
            scores.extend(
                [
                    field(key.replace("_", " ").title(), self.dimensions[key]),
                    Label(DIMENSION_COPY.get(key, key)),
                    Label(partial(meter, key)),
                ]
            )
        return [
            ScrollablePane(
                HSplit(
                    [
                        Label("Add a fully synthetic report. No real/private report import."),
                        field("Report path", self.path_input),
                        Label(self.source_description),
                        field("Fixture slug (not the canonical- prefix)", self.slug_input),
                        Label(self.destination_description),
                        Label(
                            "Continue checks source, slug and collision using the existing core."
                        ),
                    ]
                )
            ),
            ScrollablePane(
                HSplit(
                    [
                        field("How should this report be triaged?", self.classes),
                        Label(
                            lambda: (
                                "Expected: "
                                + canonical_expected_decision(self.classes.current_value).value
                            )
                        ),
                        field("Reproducible", self.reproducible),
                        field("Impact", self.impact),
                        field("Ground-truth rationale", self.rationale),
                        field("Sanitization note", self.note),
                    ]
                )
            ),
            ScrollablePane(
                HSplit(
                    [
                        Label(
                            "Select required evidence. Found headings are structural "
                            "detection, NOT proof of truth."
                        ),
                        self.evidence,
                        Label(self.evidence_description),
                        field("Disallowed claims (one per line; optional)", self.claims),
                    ]
                )
            ),
            ScrollablePane(HSplit(scores)),
            HSplit([self.review, self.confirm], padding=1),
            self.success.__pt_container__(),
        ]

    def source_description(self) -> str:
        if self.source is not None and str(self.source.path) == str(
            Path(self.path_input.text).absolute()
        ):
            return display_text("Detected H1: " + self.source.title)
        return "H1: not checked for this path yet. Continue reads it with the core parser."

    def destination_description(self) -> str:
        if self.source is None:
            return "Generated ID and destination will appear after the report is read."
        try:
            manifest = core.build_manifest(
                self.source,
                slug=self.slug_input.text,
                report_class=ReportClass.REVIEW,
                ground_truth=GroundTruth(),
            )
        except core.AddReportError as error:
            return (
                display_text("[!] " + str(error))
                if self.slug_input.text
                else "Enter a fixture slug."
            )
        return display_text(
            f"Generated ID: {manifest.id}\n"
            f"Destination: {self.session.corpus / Path(manifest.report.path).parent}"
        )

    def evidence_description(self) -> str:
        found = self.source.evidence_keys if self.source is not None else ()
        return "\n".join(
            f"{'[OK]' if key in found else '[--]'} {key.replace('_', ' ')}: "
            f"{'heading found' if key in found else 'heading not found'}"
            for key in EVIDENCE_SECTION_PATTERNS
        )

    def _bindings(self) -> KeyBindings:
        keys = KeyBindings()

        @keys.add("tab")
        def next_field(event: KeyPressEvent) -> None:
            event.app.layout.focus_next()

        @keys.add("s-tab")
        def previous_field(event: KeyPressEvent) -> None:
            event.app.layout.focus_previous()

        @keys.add("f6")
        def previous_step(event: KeyPressEvent) -> None:
            self.back()

        @keys.add("f7")
        def next_step(event: KeyPressEvent) -> None:
            self.next()

        @keys.add("f8")
        def create(event: KeyPressEvent) -> None:
            self.create()

        @keys.add("c-c")
        @keys.add("c-q")
        def cancel(event: KeyPressEvent) -> None:
            self.cancel()

        return keys

    def _message(self, text: str) -> None:
        self.message = display_text(text)
        self.messages.text = self.message
        self.application.invalidate()

    def _show(self, step: Step) -> None:
        self.step = step
        self._message("")
        self.application.layout.focus(self.focus_targets[step])
        self.application.invalidate()

    def _schedule(self, label: str, work: Callable[[], Any], done: Callable[[Any], None]) -> None:
        if self.busy or self.closing:
            return
        self.busy = True
        self.operation_label = label
        self.waiting.text = (
            f"[..] {label}\n\nThe core operation runs off the UI event loop.\n"
            "Do not close the terminal while creation is in progress."
        )
        self.application.layout.focus(self.waiting)
        self.task = asyncio.create_task(self._perform(work, done))
        self.application.invalidate()

    async def _perform(self, work: Callable[[], Any], done: Callable[[Any], None]) -> None:
        future = asyncio.wrap_future(self.executor.submit(capture, work))
        outcome: Outcome = await settle(future)
        self.busy = False
        if self.session.result is not None:
            self.success.text = success_text(self.session.result)
            self._show(Step.SUCCESS)
            if outcome.error is not None:
                self._message("Fixture committed; additional error: " + error_text(outcome.error))
        elif outcome.error is not None:
            self.application.layout.focus(self.focus_targets[self.step])
            self._message("[!] Cannot complete this step\n" + error_text(outcome.error))
            if self.step == Step.REVIEW:
                self.review.text = (
                    "Cannot create fixture\n\n"
                    + error_text(outcome.error)
                    + "\n\nGo Back to edit, prepare and review again."
                )
                self.confirm.checked = False
        else:
            done(outcome.value)
        self.application.invalidate()

    def _loaded(self, source: core.ReportSource) -> None:
        self.source = source
        self.evidence.current_values = list(source.evidence_keys)
        self.application.layout.focus(self.slug_input)

    def _inspected(self, preview: SourcePreview) -> None:
        if (
            self.source is None
            or self.source.content != preview.source.content
            or self.source.path != preview.source.path
        ):
            self.evidence.current_values = list(preview.source.evidence_keys)
        self.preview, self.source = preview, preview.source
        self._show(Step.GROUND_TRUTH)

    def _manifest(self) -> CanonicalManifest:
        if self.source is None:
            raise core.AddReportError("Read and check the source first.")
        try:
            scores = {name: float(field.text) for name, field in self.dimensions.items()}
        except ValueError as error:
            raise core.AddReportError(
                "Each dimension needs a numeric score from 0.0 to 1.0."
            ) from error
        impact = self.impact.current_value
        ground_truth = GroundTruth(
            reproducible={"yes": True, "no": False, "unknown": None}[
                self.reproducible.current_value
            ],
            impact_class=None if impact == "unknown" else ImpactClass(impact),
            required_evidence=[
                key for key in EVIDENCE_SECTION_PATTERNS if key in self.evidence.current_values
            ],
            disallowed_claims=[line for line in self.claims.text.splitlines() if line],
            expected_dimensions=scores,
            rationale=self.rationale.text,
        )
        return core.build_manifest(
            self.source,
            slug=self.slug_input.text,
            report_class=self.classes.current_value,
            ground_truth=ground_truth,
            sanitization_note=self.note.text,
        )

    def next(self) -> None:
        if self.busy or self.closing or self.step >= Step.REVIEW:
            return
        if not self.usable_size:
            self._message("[!] Enlarge the terminal to at least 70 x 20 before continuing.")
            return
        if self.step == Step.SOURCE:
            path, slug = Path(self.path_input.text), self.slug_input.text
            self._schedule(
                "Checking source and destination",
                lambda: self.session.inspect_source(path, slug),
                self._inspected,
            )
        elif self.step == Step.DIMENSIONS:
            try:
                manifest = self._manifest()
            except (core.AddReportError, ValidationError) as error:
                self._message("[!] Check annotations\n" + error_text(error))
                return
            source = self.source
            assert source is not None
            self.confirm.checked = False
            self.review.text = "Preparing review..."
            self._show(Step.REVIEW)
            self._schedule(
                "Preparing full corpus preflight",
                lambda: self.session.prepare(source, manifest),
                self._prepared,
            )
        else:
            self._show(Step(self.step + 1))

    def _prepared(self, prepared: core.PreparedReport) -> None:
        self.review.text = review_text(prepared)
        self.application.layout.focus(self.review)

    def back(self) -> None:
        if self.busy or self.closing or self.step in (Step.SOURCE, Step.SUCCESS):
            return
        target = Step(self.step - 1)
        if self.step == Step.REVIEW:
            self.confirm.checked = False
            self._schedule(
                "Closing previous review", self.session.close, lambda _: self._show(target)
            )
        else:
            self._show(target)

    def create(self) -> None:
        if not self.can_create or not self.usable_size:
            return
        if not self.confirm.checked:
            self._message(
                "[!] Explicit approval required. Select the confirmation checkbox, "
                "then Create fixture."
            )
            self.application.layout.focus(self.confirm)
            return
        self._schedule(
            "Creating fixture - operation will not be abandoned",
            self.session.commit,
            lambda _: None,
        )

    def cancel(self) -> None:
        if self.busy:
            self._message(
                "[!] Operation in progress. It will finish safely; "
                "inspect the result before closing."
            )
            return
        if self.step == Step.SUCCESS:
            self.application.exit()
        else:
            self._schedule(
                "Closing preparation", self.session.close, lambda _: self.application.exit()
            )

    async def run_async(self) -> core.AddReportResult | None:
        """Drain on terminal EOF, external task cancellation and ordinary shutdown.

        UI tasks are intentionally NOT framework background tasks: frameworks
        cancel those on exit. We own and join them, then close the core scope on
        the same executor before releasing the thread. No daemon transaction.
        """
        interrupted: BaseException | None = None
        try:
            await self.application.run_async(
                pre_run=lambda: self._schedule(
                    "Reading report H1",
                    lambda: core.read_report(Path(self.path_input.text)),
                    self._loaded,
                ),
                set_exception_handler=False,
            )
        except BaseException as error:
            interrupted = error
        finally:
            self.closing = True
            # A presentation callback can fail after preparation succeeded.
            # Even then, close the scope and join the worker, not just the UI.
            try:
                if self.task is not None:
                    await settle(self.task)
            except BaseException as error:
                if interrupted is None:
                    interrupted = error
                else:
                    interrupted.add_note(error_text(error))
            finally:
                try:
                    outcome: Outcome = await settle(
                        asyncio.wrap_future(self.executor.submit(capture, self.session.close))
                    )
                    if outcome.error is not None:
                        if interrupted is None:
                            interrupted = outcome.error
                        else:
                            interrupted.add_note(error_text(outcome.error))
                finally:
                    self.executor.shutdown(wait=True)
        if self.session.result is not None:
            # Terminal/UI failures must not erase a verified, closed transaction.
            # Keep presentation errors separate from core cleanup warnings.
            if interrupted is not None and not isinstance(
                interrupted, (EOFError, asyncio.CancelledError)
            ):
                self.exit_notice = "Fixture committed; UI shutdown: " + error_text(interrupted)
            return self.session.result
        if interrupted is not None and not isinstance(interrupted, EOFError):
            raise core.AddReportError(
                "Report Builder stopped without a verified commit: " + error_text(interrupted)
            ) from interrupted
        return None
