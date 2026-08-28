"""Edge case tests for metric computations: ECE, ECE boundaries, and empty bundles."""

from __future__ import annotations

import pytest

from sloplab.models.enums import Decision
from sloplab.models.evaluation import DimensionScores, EvaluationResult
from sloplab.models.run import CaseRecord
from sloplab.scoring.metrics import (
    compute_calibration_error,
    compute_metrics,
    compute_over_rejection,
    compute_presentation_susceptibility,
)


def _make_dummy_record(
    case_id: str,
    decision: Decision,
    expected: Decision,
    confidence: float,
    operator: str | None = None,
    parent_id: str | None = None,
) -> CaseRecord:
    dims = {
        "reproducibility": 0.5,
        "evidence_completeness": 0.5,
        "claim_evidence_consistency": 0.5,
        "impact_calibration": 0.5,
        "scope_consistency": 0.5,
    }
    res = EvaluationResult(
        evaluator_name="eval",
        evaluator_version="1.0",
        case_id=case_id,
        decision=decision,
        confidence=confidence,
        dimensions=DimensionScores.from_dict(dims),
    )
    return CaseRecord.from_result(
        res,
        case_id=case_id,
        case_kind="mutated" if operator else "canonical",
        report_class="valid",
        expected_decision=expected,
        operator=operator,
        parent_id=parent_id,
    )


def test_compute_metrics_empty_list() -> None:
    bundle = compute_metrics([], "empty-eval")
    assert bundle.evaluator_name == "empty-eval"
    assert bundle.total_cases == 0
    assert bundle.decision_accuracy == 0.0
    assert bundle.false_reassurance_rate is None
    assert bundle.over_rejection_rate is None
    assert bundle.mutation_detection_rate is None
    assert bundle.calibration_error is None
    assert bundle.robustness_score is None


def test_calibration_error_all_perfect_accuracy_and_confidence() -> None:
    # 5 cases with confidence 1.0, all correct -> ECE must be 0.0
    records = [_make_dummy_record(f"c{i}", Decision.ACCEPT, Decision.ACCEPT, 1.0) for i in range(5)]
    ece = compute_calibration_error(records)
    assert ece == pytest.approx(0.0)


def test_calibration_error_all_wrong_at_perfect_confidence() -> None:
    # 5 cases with confidence 1.0, all wrong -> ECE must be 1.0
    records = [_make_dummy_record(f"c{i}", Decision.REJECT, Decision.ACCEPT, 1.0) for i in range(5)]
    ece = compute_calibration_error(records)
    assert ece == pytest.approx(1.0)


def test_over_rejection_rate_when_no_accept_cases() -> None:
    # Only cases expected to be REJECT
    records = [
        _make_dummy_record("c1", Decision.REJECT, Decision.REJECT, 0.8),
        _make_dummy_record("c2", Decision.REJECT, Decision.REJECT, 0.9),
    ]
    rate, count = compute_over_rejection(records)
    assert rate is None
    assert count == 0


def test_presentation_susceptibility_incomplete_pair() -> None:
    # Only plain case exists, polished pair is missing -> susceptibility should be None
    records = [
        _make_dummy_record("c1", Decision.ACCEPT, Decision.REJECT, 0.8, parent_id="canon-001"),
    ]
    assert compute_presentation_susceptibility(records) is None
