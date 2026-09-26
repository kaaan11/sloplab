"""Corpus-wide identity validation for canonical IDs and derived parents."""

from __future__ import annotations

from pathlib import Path

from sloplab.corpus.loader import CanonicalFixture, DerivedFixture, discover_fixtures
from sloplab.corpus.validation import validate_corpus
from sloplab.models.enums import Decision, MutationCategory
from sloplab.models.manifest import MutationManifest, ReportRef
from tests._helpers import write_canonical_fixture


def _canonical_pair(tmp_path: Path) -> tuple[Path, list[CanonicalFixture]]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Identity report A",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "b-000",
        fixture_id="canonical-b-000",
        title="Identity report B",
        report_class="valid",
    )
    canonical, _ = discover_fixtures(corpus)
    return corpus, canonical


def _derived(
    corpus: Path,
    source: CanonicalFixture,
    *,
    parent_id: str,
    case_id: str = "mut-identity-orphan-000",
) -> DerivedFixture:
    manifest = MutationManifest(
        id=case_id,
        parent_id=parent_id,
        operator="identity-test",
        category=MutationCategory.NOISE,
        seed=1,
        variant_index=0,
        base_seed=1,
        expected_decision=Decision.ACCEPT,
        generator_version="test",
        report=ReportRef(path=f"adversarial/{case_id}/report.md"),
    )
    return DerivedFixture(
        manifest=manifest,
        report=source.report,
        directory=corpus / "adversarial" / case_id,
    )


def test_duplicate_canonical_id_reports_both_fixture_locations(tmp_path: Path) -> None:
    _corpus, canonical = _canonical_pair(tmp_path)
    first, second = canonical
    duplicate = CanonicalFixture(
        manifest=first.manifest,
        report=second.report,
        directory=second.directory,
    )

    result = validate_corpus([first, duplicate], [])

    assert not result.ok
    issues = [issue for issue in result.errors if "duplicate canonical id" in issue.message]
    assert len(issues) == 1
    assert issues[0].location == str(second.directory)
    assert first.manifest.id in issues[0].message
    assert str(first.directory) in issues[0].message


def test_orphan_derived_parent_reports_case_location_and_parent(tmp_path: Path) -> None:
    corpus, canonical = _canonical_pair(tmp_path)
    orphan = _derived(corpus, canonical[0], parent_id="canonical-missing-000")

    result = validate_corpus(canonical, [orphan])

    assert not result.ok
    issues = [issue for issue in result.errors if "does not reference" in issue.message]
    assert len(issues) == 1
    assert issues[0].location == str(orphan.directory)
    assert "canonical-missing-000" in issues[0].message


def test_valid_canonical_and_parent_links_pass_identity_validation(tmp_path: Path) -> None:
    corpus, canonical = _canonical_pair(tmp_path)
    child = _derived(
        corpus,
        canonical[0],
        parent_id=canonical[0].manifest.id,
        case_id="mut-identity-valid-000",
    )

    result = validate_corpus(canonical, [child])

    identity_errors = [
        issue
        for issue in result.errors
        if "duplicate canonical id" in issue.message or "does not reference" in issue.message
    ]
    assert identity_errors == []
