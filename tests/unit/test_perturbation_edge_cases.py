"""Edge case tests for semantic perturbation and cosine distance calculations."""

from __future__ import annotations

import pytest

from sloplab.models.enums import Decision
from sloplab.models.evaluation import DimensionScores, EvaluationResult
from sloplab.models.run import CaseRecord
from sloplab.scoring.perturbation import (
    compute_cosine_similarity,
    compute_robustness_perturbation_curve,
    compute_text_perturbation,
)


def test_empty_and_punctuation_strings() -> None:
    # Both empty -> 1.0 similarity, 0.0 perturbation
    assert compute_cosine_similarity("", "") == pytest.approx(1.0)
    assert compute_text_perturbation("", "") == pytest.approx(0.0)

    # One empty, one populated -> 0.0 similarity, 1.0 perturbation
    assert compute_cosine_similarity("vulnerability found", "") == pytest.approx(0.0)
    assert compute_text_perturbation("vulnerability found", "") == pytest.approx(1.0)

    # Punctuation only (no word characters) -> treated as empty word vectors
    assert compute_cosine_similarity("!!! ???", "--- ...") == pytest.approx(1.0)


def test_perturbation_curve_no_eligible_records() -> None:
    dims = {
        "reproducibility": 0.8,
        "evidence_completeness": 0.8,
        "claim_evidence_consistency": 0.8,
        "impact_calibration": 0.8,
        "scope_consistency": 0.8,
    }
    res = EvaluationResult(
        evaluator_name="eval",
        evaluator_version="1.0",
        case_id="c1",
        decision=Decision.ACCEPT,
        confidence=0.8,
        dimensions=DimensionScores.from_dict(dims),
    )
    # Record without perturbation_distance in metadata
    rec = CaseRecord.from_result(
        res,
        case_id="c1",
        case_kind="canonical",
        report_class="valid",
        expected_decision=Decision.ACCEPT,
    )
    curve = compute_robustness_perturbation_curve([rec])
    assert curve == []


def test_perturbation_curve_single_slice_distribution() -> None:
    dims = {
        "reproducibility": 0.8,
        "evidence_completeness": 0.8,
        "claim_evidence_consistency": 0.8,
        "impact_calibration": 0.8,
        "scope_consistency": 0.8,
    }
    records = []
    for i in range(3):
        res = EvaluationResult(
            evaluator_name="eval",
            evaluator_version="1.0",
            case_id=f"c{i}",
            decision=Decision.ACCEPT,
            confidence=0.8,
            dimensions=DimensionScores.from_dict(dims),
        )
        rec = CaseRecord.from_result(
            res,
            case_id=f"c{i}",
            case_kind="mutated",
            report_class="valid",
            expected_decision=Decision.ACCEPT,
        )
        rec.evaluation_metadata["perturbation_distance"] = 0.05
        records.append(rec)

    curve = compute_robustness_perturbation_curve(records, bins=5)
    assert len(curve) == 5
    # Bin 0 should have all 3
    assert curve[0]["count"] == 3
    assert curve[0]["accuracy"] == pytest.approx(1.0)
    # Bins 1..4 should have count 0 and accuracy None
    for b in range(1, 5):
        assert curve[b]["count"] == 0
        assert curve[b]["accuracy"] is None
