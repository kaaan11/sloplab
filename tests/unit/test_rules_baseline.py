"""Tests for the deterministic rules-baseline evaluator."""

from __future__ import annotations

import random
from typing import Any

import pytest

from sloplab.corpus.parser import parse_report
from sloplab.evaluators.base import get_evaluator
from sloplab.models.enums import Decision
from sloplab.models.evaluation import EvaluationContext
from sloplab.mutations.operators.evidence import RemoveReproductionStep
from sloplab.mutations.operators.impact import ImpactInflation, ScopeExpansion
from sloplab.mutations.operators.presentation import ProfessionalizeLanguage

VALID_BODY = """\
# Missing authorization in DemoVault module

## Summary

The lookup endpoint returns another tenant's object when requested directly.

## Affected Component

DemoVault object lookup endpoint at https://demo.example.org.

## Affected Versions

DemoVault 2.3.0 through 2.4.1 (demo builds only).

## Preconditions

Valid low-privilege account on the demo instance.

## Reproduction Steps

1. Sign in as user A (tenant 1).
2. Send `GET /objects/42` with tenant 2 context.
3. Observe the response body.

## Observed Result

The object of tenant 2 is returned without an authorization check.

## Expected Security Boundary

Cross-tenant object reads must require tenant-scoped authorization.

## Impact

Medium confidentiality impact on demo data only.
"""

INVALID_BODY = """\
# Export lacks extra confirmation step in MockMart store

## Summary

Exporting one's own orders requires only a single click.

## Affected Component

MockMart export endpoint at https://shop.example.org/account/export.

## Affected Versions

MockMart 1.8.2.

## Preconditions

A signed-in demo account with sample orders.

## Reproduction Steps

1. Sign in to the demo store.
2. Click "Export my orders".
3. Observe the download starts immediately.

## Observed Result

The CSV downloads without any additional confirmation dialog.

## Expected Security Boundary

The data returned belongs exclusively to the authenticated caller; the flow matches
intended behavior documented by the application. No boundary between users is crossed.

## Impact

None identified; this is a product preference rather than a vulnerability.
"""


def evaluate(text: str, case_id: str = "canonical-test-001", **labels: object) -> Any:
    doc = parse_report(text, fixture_id=case_id, path="x")
    evaluator = get_evaluator("rules-baseline")
    ctx = EvaluationContext(report=doc, case_id=case_id, labels=dict(labels))
    return evaluator.evaluate(doc, ctx)


class TestCanonicalHandling:
    def test_complete_valid_report_accepted(self) -> None:
        result = evaluate(VALID_BODY)
        assert result.decision == Decision.ACCEPT

    def test_conditional_boundary_marker_after_negation_routes_to_review(self) -> None:
        text = VALID_BODY.replace(
            "Cross-tenant object reads must require tenant-scoped authorization.",
            "No security boundary between tenants is crossed if the request stays within "
            "one tenant.",
        )
        result = evaluate(text)
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW
        codes = {f.code for f in result.findings}
        assert "CONDITIONAL_BOUNDARY_STATEMENT" in codes
        assert "NO_SECURITY_BOUNDARY_STATED" not in codes

    def test_distant_condition_in_same_sentence_is_not_window_limited(self) -> None:
        text = VALID_BODY.replace(
            "Cross-tenant object reads must require tenant-scoped authorization.",
            "If the optional same-tenant profile is selected and all documented tenant "
            "controls remain active throughout this intentionally long explanatory clause, "
            "no security boundary between tenants is crossed.",
        )
        result = evaluate(text)
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW
        codes = {f.code for f in result.findings}
        assert "CONDITIONAL_BOUNDARY_STATEMENT" in codes
        assert "NO_SECURITY_BOUNDARY_STATED" not in codes

    def test_dotted_token_does_not_split_conditional_sentence(self) -> None:
        text = VALID_BODY.replace(
            "Cross-tenant object reads must require tenant-scoped authorization.",
            "If version 2.0 is used, no security boundary between tenants is crossed.",
        )
        result = evaluate(text)
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW
        codes = {f.code for f in result.findings}
        assert "CONDITIONAL_BOUNDARY_STATEMENT" in codes
        assert "NO_SECURITY_BOUNDARY_STATED" not in codes

    def test_conditional_negation_does_not_mask_unconditional_negation(self) -> None:
        text = VALID_BODY.replace(
            "Cross-tenant object reads must require tenant-scoped authorization.",
            "No security boundary between tenants is crossed if the request stays within one "
            "tenant. There is no security boundary between tenant A and tenant B.",
        )
        result = evaluate(text)
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "CONDITIONAL_BOUNDARY_STATEMENT" in codes
        assert "NO_SECURITY_BOUNDARY_STATED" in codes

    def test_separate_leading_if_sentence_does_not_condition_negation(self) -> None:
        text = VALID_BODY.replace(
            "Cross-tenant object reads must require tenant-scoped authorization.",
            "Contact support if this is unexpected. No security boundary applies.",
        )
        result = evaluate(text)
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "NO_SECURITY_BOUNDARY_STATED" in codes
        assert "CONDITIONAL_BOUNDARY_STATEMENT" not in codes

    def test_separate_followup_if_sentence_does_not_condition_negation(self) -> None:
        text = VALID_BODY.replace(
            "Cross-tenant object reads must require tenant-scoped authorization.",
            "No security boundary between tenants is crossed. If this is unexpected, "
            "contact support.",
        )
        result = evaluate(text)
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "NO_SECURITY_BOUNDARY_STATED" in codes
        assert "CONDITIONAL_BOUNDARY_STATEMENT" not in codes

    def test_unrelated_later_if_clause_does_not_condition_negation(self) -> None:
        text = VALID_BODY.replace(
            "Cross-tenant object reads must require tenant-scoped authorization.",
            "No security boundary between tenants is crossed, but contact support if this "
            "is unexpected.",
        )
        result = evaluate(text)
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "NO_SECURITY_BOUNDARY_STATED" in codes
        assert "CONDITIONAL_BOUNDARY_STATEMENT" not in codes

    def test_abbreviation_does_not_split_conditional_clause(self) -> None:
        text = VALID_BODY.replace(
            "Cross-tenant object reads must require tenant-scoped authorization.",
            "If compatibility mode is enabled, e.g. for legacy clients, no security "
            "boundary between tenants is crossed.",
        )
        result = evaluate(text)
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW
        codes = {f.code for f in result.findings}
        assert "CONDITIONAL_BOUNDARY_STATEMENT" in codes
        assert "NO_SECURITY_BOUNDARY_STATED" not in codes

    def test_parenthetical_if_does_not_condition_outer_negation(self) -> None:
        text = VALID_BODY.replace(
            "Cross-tenant object reads must require tenant-scoped authorization.",
            "No security boundary between tenants is crossed (contact support if this is "
            "unexpected).",
        )
        result = evaluate(text)
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "NO_SECURITY_BOUNDARY_STATED" in codes
        assert "CONDITIONAL_BOUNDARY_STATEMENT" not in codes

    def test_coordinated_followup_if_does_not_condition_negation(self) -> None:
        text = VALID_BODY.replace(
            "Cross-tenant object reads must require tenant-scoped authorization.",
            "No security boundary between tenants is crossed, and contact support if this "
            "is unexpected.",
        )
        result = evaluate(text)
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "NO_SECURITY_BOUNDARY_STATED" in codes
        assert "CONDITIONAL_BOUNDARY_STATEMENT" not in codes

    def test_multiple_conditional_denials_are_independently_conditional(self) -> None:
        text = VALID_BODY.replace(
            "Cross-tenant object reads must require tenant-scoped authorization.",
            "If profile A is enabled, no boundary between tenants is crossed. "
            "If profile B is enabled, no boundary between roles is crossed.",
        )
        result = evaluate(text)
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW
        codes = {f.code for f in result.findings}
        assert "CONDITIONAL_BOUNDARY_STATEMENT" in codes
        assert "NO_SECURITY_BOUNDARY_STATED" not in codes

    def test_question_newline_does_not_merge_conditional_and_unconditional_denials(
        self,
    ) -> None:
        text = VALID_BODY.replace(
            "Cross-tenant object reads must require tenant-scoped authorization.",
            "If profile A is enabled, no boundary between tenants is crossed?\n"
            "No boundary between environments is crossed!",
        )
        result = evaluate(text)
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "CONDITIONAL_BOUNDARY_STATEMENT" in codes
        assert "NO_SECURITY_BOUNDARY_STATED" in codes

    def test_applies_if_is_a_postfix_conditional_denial(self) -> None:
        text = VALID_BODY.replace(
            "Cross-tenant object reads must require tenant-scoped authorization.",
            "No security boundary applies if the feature is disabled.",
        )
        result = evaluate(text)
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW
        codes = {f.code for f in result.findings}
        assert "CONDITIONAL_BOUNDARY_STATEMENT" in codes
        assert "NO_SECURITY_BOUNDARY_STATED" not in codes

    def test_no_boundary_report_rejected(self) -> None:
        result = evaluate(INVALID_BODY)
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "NO_SECURITY_BOUNDARY_STATED" in codes


class TestMutationSensitivity:
    def test_removed_reproduction_step_not_accepted(self) -> None:
        doc = parse_report(VALID_BODY, fixture_id="canonical-t-002", path="x")
        mutated_text, _ = RemoveReproductionStep().apply(doc, random.Random(5))
        result = evaluate(mutated_text)
        assert result.decision != Decision.ACCEPT
        assert any(f.code in {"THIN_REPRO_STEPS", "EMPTY_REPRO_STEPS"} for f in result.findings)

    @pytest.mark.parametrize("op_cls", [ImpactInflation, ScopeExpansion])
    def test_impact_mutations_flagged(self, op_cls: type) -> None:
        doc = parse_report(VALID_BODY, fixture_id="canonical-t-003", path="x")
        mutated_text, params = op_cls().apply(doc, random.Random(5))
        _ = params
        result = evaluate(mutated_text)
        expected_code = (
            "IMPACT_INFLATION_LANGUAGE" if op_cls is ImpactInflation else "SCOPE_EXPANSION_CLAIM"
        )
        assert any(f.code == expected_code for f in result.findings)
        assert result.decision != Decision.ACCEPT

    def test_professionalization_does_not_change_decision(self) -> None:
        base_result = evaluate(VALID_BODY)
        doc = parse_report(VALID_BODY, fixture_id="canonical-t-004", path="x")
        polished, _ = ProfessionalizeLanguage().apply(doc, random.Random(5))
        polished_result = evaluate(polished)
        assert polished_result.decision == base_result.decision


class TestLabelIndependence:
    def test_labels_do_not_affect_output(self) -> None:
        clean = evaluate(VALID_BODY)
        labeled = evaluate(VALID_BODY, expected_decision="reject", expected_dimensions={"x": 1})
        assert clean.model_dump() == labeled.model_dump()


class TestDeterminism:
    def test_repeated_evaluation_identical(self) -> None:
        first = evaluate(VALID_BODY).model_dump()
        second = evaluate(VALID_BODY).model_dump()
        assert first == second
