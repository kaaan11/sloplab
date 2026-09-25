"""Small synthetic fixtures shared by the add-report unit/regression tests."""

from __future__ import annotations

from pathlib import Path

from sloplab.corpus.add_report import ReportSource, build_manifest, read_report
from sloplab.corpus.conventions import EVIDENCE_SECTION_PATTERNS
from sloplab.models.enums import DIMENSIONS, ReportClass
from sloplab.models.manifest import CanonicalManifest, GroundTruth
from tests._helpers import write_canonical_fixture

REPORT = "# Synthetic boundary report\n\n## Reproduction Steps\n\n1. Inspect demo data.\n"


def make_source(tmp_path: Path, content: bytes | None = None) -> ReportSource:
    path = tmp_path / "input.md"
    path.write_bytes(REPORT.encode() if content is None else content)
    return read_report(path)


def make_manifest(
    source: ReportSource,
    *,
    slug: str = "new-001",
    report_class: ReportClass = ReportClass.VALID,
    ground_truth: GroundTruth | None = None,
) -> CanonicalManifest:
    return build_manifest(
        source,
        slug=slug,
        report_class=report_class,
        ground_truth=ground_truth
        or GroundTruth(
            reproducible=True,
            required_evidence=["reproduction_steps"],
            expected_dimensions={name: 0.9 for name in DIMENSIONS},
            rationale="Fully synthetic test scenario.",
        ),
        sanitization_note="Synthetic only; no real data.",
    )


def make_corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    write_canonical_fixture(
        root, "existing", fixture_id="canonical-existing", title="Existing test"
    )
    return root


def snapshot(root: Path) -> dict[str, bytes | None]:
    """Compare names, directory existence and exact bytes (not mutable mtimes)."""
    return {
        p.relative_to(root).as_posix(): None if p.is_dir() else p.read_bytes()
        for p in sorted(root.rglob("*"))
    }


def answers(*, confirm: str | None = "y", slug: str = "new-001") -> str:
    values = [slug, "valid", "yes", "medium"]
    values.extend("y" if key == "reproduction_steps" else "n" for key in EVIDENCE_SECTION_PATTERNS)
    values += ["", *["0.9" for _ in DIMENSIONS], "Synthetic test", "Synthetic only"]
    if confirm is not None:
        values.append(confirm)
    return "\n".join(values) + "\n"
