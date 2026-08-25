"""Loading of canonical fixtures and derived (mutated) case directories."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from sloplab import __version__
from sloplab.corpus.parser import parse_report
from sloplab.models.manifest import CanonicalManifest, MutationManifest
from sloplab.models.report import ReportDocument

CANONICAL_MANIFEST_NAME = "manifest.yaml"
MUTATION_MANIFEST_NAME = "mutation-manifest.yaml"
REPORT_FILE_NAME = "report.md"

#: Marker file identifying a generated benchmark-suite output directory; such
#: directories are pruned from corpus discovery.
SUITE_INDEX_NAME = "suite-index.jsonl"


class FixtureError(Exception):
    """Raised when a fixture directory cannot be loaded, with an actionable message."""


@dataclass(frozen=True)
class CanonicalFixture:
    manifest: CanonicalManifest
    report: ReportDocument
    directory: Path

    @property
    def fixture_id(self) -> str:
        return self.manifest.id


@dataclass(frozen=True)
class DerivedFixture:
    manifest: MutationManifest
    report: ReportDocument
    directory: Path

    @property
    def case_id(self) -> str:
        return self.manifest.id


def format_validation_error(error: ValidationError) -> str:
    """Render a pydantic error as a compact actionable bullet list."""
    lines: list[str] = []
    for issue in error.errors():
        loc = ".".join(str(part) for part in issue["loc"]) or "<root>"
        lines.append(f"  - field '{loc}': {issue['msg']}")
    return "\n".join(lines)


def _read_manifest(path: Path) -> dict[str, object]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise FixtureError(f"{path}: invalid YAML ({exc})") from exc
    if not isinstance(payload, dict):
        raise FixtureError(f"{path}: manifest must be a YAML mapping, got {type(payload).__name__}")
    return payload


def _load_report_document(
    manifest_path: Path,
    corpus_root: Path,
    report_rel_path: str,
    fixture_id: str,
    fallback_title: str,
) -> tuple[ReportDocument, Path]:
    resolved = (corpus_root / report_rel_path).resolve()
    if not resolved.is_file():
        raise FixtureError(
            f"{manifest_path}: 'report.path' points to missing file '{report_rel_path}' "
            f"(resolved: {resolved})"
        )
    raw = resolved.read_text(encoding="utf-8")
    doc = parse_report(raw, fixture_id=fixture_id, path=str(Path(report_rel_path)))
    if not any(s.level == 1 for s in doc.sections):
        raise FixtureError(
            f"{resolved}: report has no H1 heading; expected title '{fallback_title}'"
        )
    return doc, resolved


def load_canonical_fixture(fixture_dir: Path, corpus_root: Path | None = None) -> CanonicalFixture:
    """Load one canonical fixture directory containing manifest.yaml + report.md."""
    root = corpus_root if corpus_root is not None else fixture_dir.parent
    manifest_path = fixture_dir / CANONICAL_MANIFEST_NAME
    if not manifest_path.is_file():
        alt = sorted(fixture_dir.glob("*.yaml"))
        hint = f" (found: {[p.name for p in alt]})" if alt else ""
        raise FixtureError(f"{fixture_dir}: missing {CANONICAL_MANIFEST_NAME}{hint}")

    payload = _read_manifest(manifest_path)
    try:
        manifest = CanonicalManifest.model_validate(payload)
    except ValidationError as exc:
        raise FixtureError(
            f"{manifest_path}: manifest validation failed\n{format_validation_error(exc)}"
        ) from exc

    expected_dir_name = manifest.id.removeprefix("canonical-")
    if fixture_dir.name != expected_dir_name and fixture_dir.name != manifest.id:
        raise FixtureError(
            f"{manifest_path}: manifest id '{manifest.id}' does not match "
            f"directory name '{fixture_dir.name}'"
        )

    doc, _ = _load_report_document(
        manifest_path,
        root,
        manifest.report.path,
        manifest.id,
        manifest.title,
    )
    h1 = next((s.heading for s in doc.sections if s.level == 1 and s.heading), "")
    if h1 != manifest.title:
        raise FixtureError(
            f"{manifest_path}: manifest title {manifest.title!r} does not match report "
            f"H1 heading {h1!r}"
        )
    return CanonicalFixture(manifest=manifest, report=doc, directory=fixture_dir)


def load_derived_fixture(case_dir: Path, corpus_root: Path | None = None) -> DerivedFixture:
    """Load one derived case directory containing mutation-manifest.yaml + report.md."""
    root = corpus_root if corpus_root is not None else case_dir.parent.parent
    manifest_path = case_dir / MUTATION_MANIFEST_NAME
    if not manifest_path.is_file():
        raise FixtureError(f"{case_dir}: missing {MUTATION_MANIFEST_NAME}")

    payload = _read_manifest(manifest_path)
    try:
        manifest = MutationManifest.model_validate(payload)
    except ValidationError as exc:
        raise FixtureError(
            f"{manifest_path}: manifest validation failed\n{format_validation_error(exc)}"
        ) from exc

    doc, _ = _load_report_document(
        manifest_path,
        root,
        manifest.report.path,
        manifest.id,
        manifest.id,
    )
    return DerivedFixture(manifest=manifest, report=doc, directory=case_dir)


def discover_fixtures(corpus_root: Path) -> tuple[list[CanonicalFixture], list[DerivedFixture]]:
    """Recursively discover canonical fixtures and derived cases under a root.

    Directories containing a generated ``suite-index.jsonl`` (benchmark outputs) are
    skipped entirely so that re-running over an extended corpus stays consistent.
    """
    canonical: list[CanonicalFixture] = []
    derived: list[DerivedFixture] = []
    for dirpath, dirnames, filenames in os.walk(corpus_root):
        dirnames.sort()
        if SUITE_INDEX_NAME in filenames:
            dirnames[:] = []  # generated benchmark output; do not descend
            continue
        path = Path(dirpath)
        if CANONICAL_MANIFEST_NAME in filenames:
            canonical.append(load_canonical_fixture(path, corpus_root))
        elif MUTATION_MANIFEST_NAME in filenames:
            derived.append(load_derived_fixture(path, corpus_root))
    canonical.sort(key=lambda f: f.fixture_id)
    derived.sort(key=lambda c: c.case_id)
    return canonical, derived


def load_corpus_version() -> str:
    """Package version stamped into manifests generated by this build."""
    return __version__
