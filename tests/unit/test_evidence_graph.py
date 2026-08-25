"""Tests for the evidence-graph baseline evaluator (V23)."""

from __future__ import annotations

from typing import Any

import pytest

from sloplab.corpus.parser import parse_report
from sloplab.evaluators.base import get_evaluator
from sloplab.models.enums import Decision
from sloplab.models.evaluation import EvaluationContext

VALID_BODY = """\
# Missing authorization in DemoVault module

## Summary

The lookup endpoint returns another tenant's object, causing cross-tenant disclosure.

## Affected Component

DemoVault document lookup endpoint at https://demo.example.org.

## Affected Versions

DemoVault 2.3.0 through 2.4.1.

## Preconditions

A viewer-tier account on tenant A.

## Reproduction Steps

1. Sign in as tenant A viewer.
2. Request GET /api/v1/documents/1042.
3. Observe the response body.

## Observed Result

Tenant B's document content is returned to the tenant A session.

## Expected Security Boundary

Object reads must be scoped to the caller's tenant; cross-tenant reads require
tenant-scoped authorization.

## Impact

Medium confidentiality impact through unauthorized information disclosure.
"""

NO_CLAIM_BODY = """# Bare note\n\nNothing here at all.\n"""


def evaluate(text: str, case_id: str = "canonical-t-100", **labels: object) -> Any:
    doc = parse_report(text, fixture_id=case_id, path="x")
    evaluator = get_evaluator("evidence-graph-baseline")
    ctx = EvaluationContext(report=doc, case_id=case_id, labels=dict(labels))
    return evaluator.evaluate(doc, ctx)


class TestGraphExtraction:
    def test_complete_graph_accepted(self) -> None:
        result = evaluate(VALID_BODY)
        assert result.decision == Decision.ACCEPT
        assert result.metadata["edges"] == 4

    def test_missing_claim_report_routes_to_review(self) -> None:
        result = evaluate(NO_CLAIM_BODY)
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW
        codes = {f.code for f in result.findings}
        assert "GRAPH_MISSING_IMPACT_CLAIM" in codes

    def test_negated_boundary_rejects(self) -> None:
        text = VALID_BODY.replace(
            "Object reads must be scoped",
            "No security boundary applies. Object reads must be scoped",
        )
        result = evaluate(text)
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "BOUNDARY_NEGATED_BY_AUTHOR" in codes

    def test_hedged_report_never_accepts(self) -> None:
        hedged = VALID_BODY.replace(
            "Medium confidentiality impact",
            "Impact is undetermined without maintainer input; "
            "medium confidentiality impact suspected",
        )
        result = evaluate(hedged)
        assert result.decision != Decision.ACCEPT


class TestLabelIndependence:
    def test_labels_do_not_affect_output(self) -> None:
        clean = evaluate(VALID_BODY).model_dump()
        labeled = evaluate(
            VALID_BODY,
            expected_decision="reject",
            expected_dimensions={"reproducibility": 0.1},
            mutation_ground_truth={"anything": True},
        ).model_dump()
        assert clean == labeled


class TestContractConformance:
    def test_result_shape_matches_normalized_contract(self) -> None:
        from sloplab.models.evaluation import EvaluationResult

        result = evaluate(VALID_BODY)
        assert isinstance(result, EvaluationResult)
        assert 0.0 <= result.confidence <= 1.0
        assert set(result.dimensions.as_dict()) == {
            "reproducibility",
            "evidence_completeness",
            "claim_evidence_consistency",
            "impact_calibration",
            "scope_consistency",
        }

    def test_deterministic(self) -> None:
        first = evaluate(VALID_BODY).model_dump()
        second = evaluate(VALID_BODY).model_dump()
        assert first == second

    @pytest.mark.parametrize(
        "body",
        [NO_CLAIM_BODY, "", "# Only a title\n"],
    )
    def test_degrades_gracefully_on_minimal_reports(self, body: str) -> None:
        result = evaluate(body)
        assert result.decision in (
            Decision.NEEDS_MANUAL_REVIEW,
            Decision.REJECT,
            Decision.ACCEPT,
        )
