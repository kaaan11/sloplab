"""E5b-r1: splice authorization bound to the span's source identity."""

from __future__ import annotations

import pytest

from sloplab.corpus.parser import parse_report
from sloplab.models.report import ReportDocument, ReportSection
from sloplab.mutations.textops import (
    StaleSpanError,
    document_identity,
    first_matching_section,
    remove_section,
    replace_section_body,
)


def _repro_section(doc: ReportDocument) -> ReportSection:
    section = first_matching_section(doc, "reproduction")
    assert section is not None
    return section


def _doc_pair() -> tuple[ReportDocument, ReportDocument]:
    """Two parents sharing target-section bytes/location, differing elsewhere."""
    head = "# T\n\n## Reproduction Steps\n\n1. one\n   cont\n\n2. two\n"
    target = _doc_pair_target(head, "Other A is here.\n")
    foreign = _doc_pair_target(head, "Other B is different.\n")
    assert document_identity(target) != document_identity(foreign)
    assert _repro_section(target).location == _repro_section(foreign).location
    assert _repro_section(target).text == _repro_section(foreign).text
    return target, foreign


def _doc_pair_target(head: str, tail: str) -> ReportDocument:
    return parse_report(f"{head}\n## Other\n\n{tail}", fixture_id="p", path="p")


def test_foreign_span_rejected_on_both_paths() -> None:
    """Reviewer counterexample: same bytes/location, different full identity."""
    target, foreign = _doc_pair()
    foreign_section = _repro_section(foreign)
    foreign_identity = document_identity(foreign)
    assert foreign_identity != document_identity(target)
    with pytest.raises(StaleSpanError):
        replace_section_body(
            target, foreign_section, "x", expected_document_identity=foreign_identity
        )
    with pytest.raises(StaleSpanError):
        remove_section(target, foreign_section, expected_document_identity=foreign_identity)


def test_fresh_immediate_parent_succeeds_on_both_paths() -> None:
    """Fresh span + source identity splices on both paths."""
    target, _ = _doc_pair()
    section = _repro_section(target)
    identity = document_identity(target)
    out = replace_section_body(target, section, "1. fresh\n", expected_document_identity=identity)
    assert "1. fresh" in out and "1. one" not in out
    assert "## Other" in remove_section(target, section, expected_document_identity=identity)


def test_mutated_span_and_identity_rejected() -> None:
    """Post-mutation reuse of the old span/identity pair refuses."""
    target, _ = _doc_pair()
    section = _repro_section(target)
    identity = document_identity(target)
    changed_text = replace_section_body(
        target, section, "1. fresh\n", expected_document_identity=identity
    )
    changed = parse_report(changed_text, fixture_id="p", path="p")
    with pytest.raises(StaleSpanError):
        replace_section_body(changed, section, "x", expected_document_identity=identity)
    with pytest.raises(StaleSpanError):
        remove_section(changed, section, expected_document_identity=identity)


def test_grandparent_span_and_identity_rejected() -> None:
    """Second-generation reuse of the grandparent pair refuses."""
    target, _ = _doc_pair()
    grandparent_section = _repro_section(target)
    grandparent_identity = document_identity(target)
    first_text = replace_section_body(
        target,
        grandparent_section,
        "1. fresh\n",
        expected_document_identity=grandparent_identity,
    )
    child = parse_report(first_text, fixture_id="p", path="p")
    child_section = _repro_section(child)
    child_identity = document_identity(child)
    second_text = replace_section_body(
        child, child_section, "1. newer\n", expected_document_identity=child_identity
    )
    grandchild = parse_report(second_text, fixture_id="p", path="p")
    with pytest.raises(StaleSpanError):
        replace_section_body(
            grandchild,
            grandparent_section,
            "x",
            expected_document_identity=grandparent_identity,
        )
    with pytest.raises(StaleSpanError):
        remove_section(
            grandchild, grandparent_section, expected_document_identity=grandparent_identity
        )
