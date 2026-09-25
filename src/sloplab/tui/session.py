"""Own a core preparation scope across UI events; no parallel domain rules.

All methods are synchronous and are called on the builder's single executor
thread. The UI owns scheduling; only the existing core owns files/transactions.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from sloplab.corpus import add_report as core
from sloplab.models.enums import ReportClass
from sloplab.models.manifest import CanonicalManifest, GroundTruth


@dataclass(frozen=True)
class SourcePreview:
    source: core.ReportSource
    fixture_id: str
    destination: Path


class BuilderSession:
    """One active review; editing/cancel/shutdown must close it before reuse."""

    def __init__(self, corpus: Path) -> None:
        self.corpus = corpus
        self.prepared: core.PreparedReport | None = None
        self.result: core.AddReportResult | None = None
        self._scope: ExitStack | None = None

    def inspect_source(self, path: Path, slug: str) -> SourcePreview:
        """Early H1/slug/collision feedback via the public core, not UI checks.

        Core has no separate public collision API. A short-lived preparation
        with empty review annotations checks the source and corpus, then closes.
        It is NOT the final annotated review and is never eligible for commit.
        """
        source = core.read_report(path)
        manifest = core.build_manifest(
            source, slug=slug, report_class=ReportClass.REVIEW, ground_truth=GroundTruth()
        )
        with core.prepare_add_report(source, manifest, self.corpus) as prepared:
            preview = SourcePreview(source, manifest.id, prepared.destination)
        return preview

    def prepare(
        self, source: core.ReportSource, manifest: CanonicalManifest
    ) -> core.PreparedReport:
        self.close()
        scope = ExitStack()
        try:
            prepared = scope.enter_context(core.prepare_add_report(source, manifest, self.corpus))
        except BaseException:
            scope.close()
            raise
        self._scope, self.prepared = scope, prepared
        return prepared

    def close(self, error: BaseException | None = None) -> None:
        """Invalidate the UI handle first; preserve primary error/cleanup notes."""
        scope, self._scope = self._scope, None
        self.prepared = None
        if scope is not None:
            scope.__exit__(
                type(error) if error is not None else None,
                error,
                error.__traceback__ if error is not None else None,
            )

    def commit(self) -> core.AddReportResult:
        """Called only by explicit UI confirmation. Close before exposing result."""
        prepared = self.prepared
        if prepared is None:
            raise core.AddReportError("No active review. Prepare and review the fixture first.")
        try:
            core.commit_add_report(prepared, confirmed=True)
        except BaseException as error:
            try:
                self.close(error)
            finally:
                self.result = prepared.commit_result
            raise
        else:
            try:
                self.close()
            finally:
                # Read the retained SAME result only after scope exit: stage
                # cleanup may just have appended a warning to this object.
                self.result = prepared.commit_result
        assert self.result is not None
        return self.result
