"""Click presentation layer for the shared add-report transaction API."""

from __future__ import annotations

from pathlib import Path

import click
from pydantic import ValidationError

from sloplab.corpus.add_report import (
    AddReportError,
    ReportSource,
    build_manifest,
    commit_add_report,
    prepare_add_report,
    read_report,
)
from sloplab.corpus.conventions import EVIDENCE_SECTION_PATTERNS
from sloplab.models.enums import DIMENSIONS, ImpactClass, ReportClass, canonical_expected_decision
from sloplab.models.manifest import GroundTruth


def _slug(source: ReportSource) -> str:
    # A bad H1 (e.g. too short for CanonicalManifest.title) cannot be fixed by
    # choosing another slug. Fail once rather than trapping the user in a loop.
    build_manifest(
        source, slug="preview", report_class=ReportClass.REVIEW, ground_truth=GroundTruth()
    )
    while True:
        value = str(click.prompt("Fixture slug", type=str))
        try:
            build_manifest(
                source, slug=value, report_class=ReportClass.REVIEW, ground_truth=GroundTruth()
            )
        except AddReportError as exc:
            click.echo(str(exc), err=True)
        else:
            return value


def _dimension(name: str) -> float:
    while True:
        value = float(click.prompt(name, type=click.FloatRange(0.0, 1.0)))
        try:
            GroundTruth(expected_dimensions={name: value})
        except ValidationError:
            click.echo("Enter a finite score within [0, 1].", err=True)
        else:
            return value


def run_add_report(report: Path, corpus: Path) -> None:
    """Collect annotations; keep all filesystem/domain operations in the core."""
    try:
        source = read_report(report)
        click.echo("Add a fully synthetic canonical report (no real/private report import).")
        click.echo(f"Detected H1: {source.title}")
        slug = _slug(source)
        descriptions = {
            ReportClass.VALID: "expected to be accepted as written",
            ReportClass.INVALID: "should be rejected as written",
            ReportClass.REVIEW: "genuinely ambiguous evidence; needs human review",
        }
        for report_class in ReportClass:
            click.echo(
                f"  {report_class.value} -> {canonical_expected_decision(report_class).value}: "
                f"{descriptions[report_class]}"
            )
        selected_class = ReportClass(
            click.prompt("Report class", type=click.Choice([c.value for c in ReportClass]))
        )
        reproducible = click.prompt(
            "Reproducible", type=click.Choice(["yes", "no", "unknown"]), default="unknown"
        )
        impact = click.prompt(
            "Impact class",
            type=click.Choice([c.value for c in ImpactClass] + ["unknown"]),
            default="unknown",
        )
        click.echo("Required evidence (detected headings are shown; you author the requirements):")
        evidence = [
            key
            for key in EVIDENCE_SECTION_PATTERNS
            if click.confirm(
                f"Require {key} ({'found' if key in source.evidence_keys else 'not found'})?",
                default=key in source.evidence_keys,
            )
        ]
        click.echo("Disallowed claims: one per line; an empty line finishes.")
        claims: list[str] = []
        while claim := click.prompt("Disallowed claim", default="", show_default=False):
            claims.append(claim)
        dimensions = {dimension: _dimension(dimension) for dimension in DIMENSIONS}
        rationale = click.prompt("Ground-truth rationale", default="", show_default=False)
        note = click.prompt("Sanitization note", default="", show_default=False)
        manifest = build_manifest(
            source,
            slug=slug,
            report_class=selected_class,
            ground_truth=GroundTruth(
                reproducible={"yes": True, "no": False, "unknown": None}[reproducible],
                impact_class=None if impact == "unknown" else ImpactClass(impact),
                required_evidence=evidence,
                disallowed_claims=claims,
                expected_dimensions=dimensions,
                rationale=rationale,
            ),
            sanitization_note=note,
        )
        with prepare_add_report(source, manifest, corpus) as prepared:
            click.echo("\nManifest preview:\n" + prepared.manifest_text)
            click.echo(f"Destination: {prepared.destination}")
            click.echo(f"Expected decision: {prepared.manifest.expected_decision().value}")
            click.echo("Full corpus preflight:\n" + prepared.preflight.render())
            if not click.confirm(
                "Confirm this report is synthetic and create this fixture?", default=False
            ):
                click.echo("Cancelled; corpus unchanged.")
                return
            result = commit_add_report(prepared, confirmed=True)
        click.echo(f"\nFixture added: {result.fixture_id}\n{result.destination}")
        click.echo(f"report.md copied: {result.report_path}")
        click.echo(f"manifest.yaml generated: {result.manifest_path}")
        click.echo(
            f"Canonical fixtures: {result.before_count} -> {result.validation.checked_canonical}"
        )
        click.echo("Full corpus validation:\n" + result.validation.render())
        click.echo("Next: run the full suite (its YAML corpus_root must point to this corpus):")
        click.echo(
            "sloplab benchmark benchmarks/suites/v1-core.yaml "
            "--evaluator rules-baseline --out benchmarks/results/new-report-run"
        )
        click.echo(
            "Before committing corpus changes, update README/docs/dataset-card.md counts "
            "and regenerate reference results/docs where needed."
        )
    except (AddReportError, ValidationError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
