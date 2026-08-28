"""Tests for mutation operator edge cases, empty documents, and missing sections."""

from __future__ import annotations

import random

import pytest

from sloplab.models.report import ReportDocument
from sloplab.mutations.base import get_operator, list_operators
from sloplab.mutations.operators.injection import (
    EvaluatorOverrideInjection,
    MarkdownPolyglotInjection,
)


def _empty_doc() -> ReportDocument:
    return ReportDocument(
        fixture_id="empty-001",
        path="empty.md",
        raw_text="No headings here.",
        title="Empty",
        sections=(),
    )


def test_injection_operators_target_section_missing() -> None:
    doc = _empty_doc()
    rng = random.Random(42)

    op_override = EvaluatorOverrideInjection()
    mutated_text, params = op_override.apply(doc, rng)
    assert mutated_text == doc.raw_text
    assert params["injected"] is False
    assert params["reason"] == "no_target_section"

    op_polyglot = MarkdownPolyglotInjection()
    mutated_text_p, params_p = op_polyglot.apply(doc, rng)
    assert mutated_text_p == doc.raw_text
    assert params_p["injected"] is False
    assert params_p["reason"] == "no_target_section"


def test_injection_operators_with_explicit_directive_index() -> None:
    from sloplab.corpus.parser import parse_report

    raw = "## Summary\n\nSome summary here.\n\n## Reproduction Steps\n\n1. Step one."
    parsed = parse_report(raw, fixture_id="valid-001", path="valid.md")

    op_override = EvaluatorOverrideInjection()
    mutated, params = op_override.apply(parsed, random.Random(1), parameters={"directive_index": 0})
    assert params["injected"] is True
    assert params["directive_index"] == 0
    assert "INTERNAL SYSTEM DIRECTIVE" in mutated

    mutated1, params1 = op_override.apply(
        parsed, random.Random(1), parameters={"directive_index": 1}
    )
    assert params1["injected"] is True
    assert params1["directive_index"] == 1
    assert "Security Evaluation Instructions" in mutated1


def test_all_registered_operators_graceful_on_empty_document() -> None:
    """Every registered operator must handle documents without target sections safely."""
    doc = _empty_doc()
    rng = random.Random(12345)

    for op_name in list_operators():
        op = get_operator(op_name)
        try:
            mutated, params = op.apply(doc, rng)
            assert isinstance(mutated, str)
            assert isinstance(params, dict)
        except Exception as exc:  # pragma: no cover
            pytest.fail(f"Operator '{op_name}' crashed on empty document: {exc}")
