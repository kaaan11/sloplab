"""Hand-crafted mutation-family tests for evidence-graph-baseline (V26 audit).

Four families, each with a hand-built minimal report:

- contradict_observed_result  -> MUST CATCH (reject): the observation undermines
  the claim, breaking the "supports" edge (contract conformance fix).
- remove_reproduction_step    -> MUST CATCH downgrade: dropping below the support
  floor weakens the reproduction edge; acceptance is no longer available.
- fabricate_reference         -> NEGATIVE CONTROL: outside the structural contract;
  the evaluator stays unchanged by design.
- impact_inflation            -> NEGATIVE CONTROL: same as above.

The two negative-control cases exist to pin the documented blindness so any future
accidental capability change is visible in review.
"""

from __future__ import annotations

import random
from typing import Any

from sloplab.corpus.parser import parse_report
from sloplab.evaluators.base import get_evaluator
from sloplab.models.enums import Decision
from sloplab.models.evaluation import EvaluationContext
from sloplab.mutations.operators.evidence import RemoveReproductionStep
from sloplab.mutations.operators.impact import ImpactInflation
from sloplab.mutations.operators.references import FabricateReference

TWO_STEP_BODY = """\
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

## Observed Result

Tenant B's document content is returned to the tenant A session.

## Expected Security Boundary

Object reads must be scoped to the caller's tenant.

## Impact

Medium confidentiality impact through unauthorized information disclosure.
"""


def evaluate(text: str, case_id: str = "canonical-t-200") -> Any:
    doc = parse_report(text, fixture_id=case_id, path="x")
    evaluator = get_evaluator("evidence-graph-baseline")
    ctx = EvaluationContext(report=doc, case_id=case_id)
    return evaluator.evaluate(doc, ctx)


class TestFamilyContradictObservedResult:
    def test_undermined_observation_must_be_caught(self) -> None:
        mutated = TWO_STEP_BODY.replace(
            "Tenant B's document content is returned to the tenant A session.",
            "Tenant B's document content is returned to the tenant A session. However, "
            "on repeated verification the endpoint returned 403 and no cross-tenant "
            "data was returned.",
        )
        result = evaluate(mutated)
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "GRAPH_OBSERVED_UNDERMINES_CLAIM" in codes


class TestFamilyRemoveReproductionStep:
    def test_below_support_floor_downgrades_accept(self) -> None:
        doc = parse_report(TWO_STEP_BODY, fixture_id="canonical-t-201", path="x")
        assert evaluate(TWO_STEP_BODY).decision == Decision.ACCEPT  # baseline accepts

        mutated_text, params = RemoveReproductionStep().apply(doc, random.Random(5))
        _ = params
        result = evaluate(mutated_text)
        # One step remains: below the support floor -> acceptance unavailable.
        assert result.decision != Decision.ACCEPT


class TestNegativeControlFamilies:
    def test_fabricate_reference_is_invisible_by_design(self) -> None:
        baseline_decision = evaluate(TWO_STEP_BODY).decision
        doc = parse_report(TWO_STEP_BODY, fixture_id="canonical-t-202", path="x")
        mutated_text, _ = FabricateReference().apply(doc, random.Random(3))
        result = evaluate(mutated_text)
        assert result.decision == baseline_decision  # pinned negative control

    def test_impact_inflation_is_invisible_by_design(self) -> None:
        baseline_decision = evaluate(TWO_STEP_BODY).decision
        doc = parse_report(TWO_STEP_BODY, fixture_id="canonical-t-203", path="x")
        mutated_text, _ = ImpactInflation().apply(doc, random.Random(3))
        result = evaluate(mutated_text)
        assert result.decision == baseline_decision  # pinned negative control
