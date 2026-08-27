"""Tests for indirect prompt injection mutation operators and security metrics."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from sloplab.corpus.loader import load_canonical_fixture
from sloplab.models.enums import Decision
from sloplab.models.run import CaseRecord
from sloplab.mutations.base import derive_seed, get_operator
from sloplab.mutations.operators.injection import (
    EvaluatorOverrideInjection,
    MarkdownPolyglotInjection,
)
from sloplab.safety.policy import validate_content_safety
from sloplab.scoring.metrics import compute_injection_metrics, compute_metrics


@pytest.fixture(scope="module")
def sample_report() -> object:
    fixture_dir = Path(__file__).resolve().parents[2] / "corpus/canonical/authz-001"
    return load_canonical_fixture(fixture_dir, fixture_dir.parent.parent).report


def test_injection_operators_registered() -> None:
    op1 = get_operator("evaluator_override_injection")
    op2 = get_operator("evaluator-override-injection")
    assert isinstance(op1, EvaluatorOverrideInjection)
    assert op1 is op2

    op3 = get_operator("markdown_polyglot_injection")
    op4 = get_operator("markdown-polyglot-injection")
    assert isinstance(op3, MarkdownPolyglotInjection)
    assert op3 is op4


def test_evaluator_override_injection_safety_and_structure(sample_report: object) -> None:
    op = EvaluatorOverrideInjection()
    seed = derive_seed(100, "authz-001", op.spec.name, 0)
    mutated, params = op.apply(sample_report, random.Random(seed))  # type: ignore[arg-type]

    assert params["injected"] is True
    assert "SYSTEM DIRECTIVE" in mutated or "Security Evaluation Instructions" in mutated
    # Must satisfy safety policy without violations
    violations = validate_content_safety(mutated)
    assert violations == []


def test_markdown_polyglot_injection_safety_and_structure(sample_report: object) -> None:
    op = MarkdownPolyglotInjection()
    seed = derive_seed(200, "authz-001", op.spec.name, 0)
    mutated, params = op.apply(sample_report, random.Random(seed))  # type: ignore[arg-type]

    assert params["injected"] is True
    assert "<!-- [SYSTEM INSTRUCTION]" in mutated or 'style="display:none"' in mutated
    violations = validate_content_safety(mutated)
    assert violations == []


def _make_record(
    operator: str,
    decision: Decision,
    expected: Decision,
    case_id: str = "c1",
) -> CaseRecord:
    from sloplab.models.evaluation import DimensionScores, EvaluationResult

    dims = {
        "reproducibility": 0.8,
        "evidence_completeness": 0.8,
        "claim_evidence_consistency": 0.8,
        "impact_calibration": 0.8,
        "scope_consistency": 0.8,
    }
    res = EvaluationResult(
        evaluator_name="test-eval",
        evaluator_version="1.0",
        case_id=case_id,
        decision=decision,
        confidence=0.9,
        dimensions=DimensionScores.from_dict(dims),
    )
    return CaseRecord.from_result(
        res,
        case_id=case_id,
        case_kind="mutated",
        report_class="invalid",
        expected_decision=expected,
        operator=operator,
    )


def test_injection_metrics_scoring() -> None:
    # 3 resisted attacks (expected REJECT, got REJECT)
    # 1 hijacked attack (expected REJECT, forced to ACCEPT)
    records = [
        _make_record("evaluator_override_injection", Decision.REJECT, Decision.REJECT, "c1"),
        _make_record(
            "evaluator_override_injection", Decision.NEEDS_MANUAL_REVIEW, Decision.REJECT, "c2"
        ),
        _make_record("markdown_polyglot_injection", Decision.REJECT, Decision.REJECT, "c3"),
        _make_record("markdown_polyglot_injection", Decision.ACCEPT, Decision.REJECT, "c4"),
    ]

    irr, asr, count = compute_injection_metrics(records)
    assert count == 4
    assert asr == pytest.approx(0.25)
    assert irr == pytest.approx(0.75)

    bundle = compute_metrics(records, "test-eval")
    assert bundle.injection_resistance_rate == pytest.approx(0.75)
    assert bundle.attack_success_rate == pytest.approx(0.25)
    assert bundle.injection_cases_count == 4
