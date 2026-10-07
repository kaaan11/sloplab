"""Plain-text UI copy and rendering. No filesystem operations or domain rules."""

from __future__ import annotations

import unicodedata

from sloplab.corpus.add_report import AddReportResult, PreparedReport
from sloplab.models.enums import (
    CLAIM_EVIDENCE_CONSISTENCY,
    EVIDENCE_COMPLETENESS,
    IMPACT_CALIBRATION,
    REPRODUCIBILITY,
    SCOPE_CONSISTENCY,
    ReportClass,
)

CLASS_COPY = {
    ReportClass.VALID: "Valid - accept as written",
    ReportClass.INVALID: "Invalid - reject as written",
    ReportClass.REVIEW: "Manual review - unresolved / insufficient decisive evidence",
}
DIMENSION_COPY = {
    REPRODUCIBILITY: "Can a reader reproduce the behavior from the report?",
    EVIDENCE_COMPLETENESS: "Does the report contain the evidence needed to assess its claim?",
    CLAIM_EVIDENCE_CONSISTENCY: "Do the claims agree with the evidence actually presented?",
    IMPACT_CALIBRATION: "Is the claimed impact proportionate to the demonstrated behavior?",
    SCOPE_CONSISTENCY: "Do affected assets and claimed scope match the evidence?",
}


def display_text(value: str) -> str:
    """Never interpret report/annotation text as terminal escapes or markup."""
    return "".join(
        char if char == "\n" or not unicodedata.category(char).startswith("C") else "?"
        for char in value
    )


def error_text(error: BaseException) -> str:
    detail = str(error) or type(error).__name__
    return display_text("\n".join([detail, *getattr(error, "__notes__", [])]))


def review_text(prepared: PreparedReport) -> str:
    manifest = prepared.manifest
    impact = manifest.ground_truth.impact_class
    return display_text(
        f"{manifest.id}\n{manifest.title}\n\n"
        f"Class: {manifest.report_class.value}\n"
        f"Expected decision: {manifest.expected_decision().value}\n"
        f"Impact: {impact.value if impact is not None else 'unknown'}\n"
        f"Destination: {prepared.destination}\n\n"
        "FIXTURE VALIDATION (actual core result)\n"
        f"{prepared.fixture_validation.render()}\n\n"
        "FULL CORPUS PREFLIGHT (existing + staged)\n"
        f"{prepared.preflight.render()}\n\n"
        f"MANIFEST PREVIEW\n{prepared.manifest_text}\n"
        "These checks validate structure and consistency, not scientific ground truth."
    )


def success_text(result: AddReportResult) -> str:
    lines = [
        "[OK] Fixture added",
        result.fixture_id,
        str(result.destination),
        "",
        f"report.md copied: {result.report_path}",
        f"manifest.yaml generated: {result.manifest_path}",
        "",
        f"Canonical fixtures: {result.before_count} -> {result.validation.checked_canonical}",
        "Full corpus validation:",
        result.validation.render(),
    ]
    if result.cleanup_warnings:
        lines += ["", "[!] Cleanup incomplete - fixture IS committed", *result.cleanup_warnings]
        lines += [
            "Do not retry add-report. Inspect remaining cleanup paths; before removing",
            "any lock, verify that no writer is active.",
        ]
    lines += [
        "",
        "Next (from the repository root):",
        "sloplab benchmark benchmarks/suites/v1-core.yaml \\",
        "  --evaluator rules-baseline --out benchmarks/results/new-report-run",
        "",
        "For a custom corpus, use a suite whose corpus_root points to that corpus.",
        "Before committing corpus changes, update README/dataset-card counts and",
        "regenerate applicable reference results/docs. No docs were edited automatically.",
    ]
    return display_text("\n".join(lines))
