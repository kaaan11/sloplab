"""Regression tests for the calibration bin-boundary defect (V21 audit finding).

Root cause: bin bounds computed via ``b * 0.1`` accumulate IEEE-754 error
(``6 * 0.1 == 0.6000000000000001``), moving boundary confidences such as 0.6 into
the previous bin and skewing ECE by ~0.01 on real data.
"""

from __future__ import annotations

import pytest

from sloplab.models.enums import Decision
from sloplab.models.run import CaseRecord
from sloplab.scoring.metrics import compute_calibration_error


def record(confidence: float, correct: bool, case_id: str) -> CaseRecord:
    dims = {
        "reproducibility": 0.9,
        "evidence_completeness": 0.9,
        "claim_evidence_consistency": 0.9,
        "impact_calibration": 0.9,
        "scope_consistency": 0.9,
    }
    from sloplab.models.evaluation import DimensionScores, EvaluationResult

    result = EvaluationResult(
        evaluator_name="t",
        evaluator_version="0",
        case_id=case_id,
        decision=Decision.ACCEPT,
        confidence=confidence,
        dimensions=DimensionScores.from_dict(dims),
    )
    # Expected decision differs from the emitted one for "incorrect" records so
    # that CaseRecord.from_result marks them as wrong.
    expected = Decision.ACCEPT if correct else Decision.REJECT
    return CaseRecord.from_result(
        result,
        case_id=case_id,
        case_kind="canonical",
        report_class="valid",
        expected_decision=expected,
    )


def test_boundary_confidence_lands_in_intended_bin() -> None:
    """Ten confident-correct cases at 0.5 plus one failing case at exactly 0.6.

    Correct binning: the 0.6 failure sits alone in bin 6 contributing
    (1/11)*|0.6-0| ; the 0.5 cases occupy bin 5 contributing (10/11)*|0.5-1|.
    The defective multiplication-based binning merged everything into bin 5.
    """
    records = [record(0.5, True, f"c{i}") for i in range(10)]
    records.append(record(0.6, False, "edge"))
    ece = compute_calibration_error(records)
    assert ece == pytest.approx((10 / 11) * 0.5 + (1 / 11) * 0.6)


def test_edge_confidences_are_captured() -> None:
    """Confidence 0.0 and 1.0 must both land in a bin (first / closed last bin)."""
    two = [record(0.0, False, "a"), record(1.0, True, "b")]
    assert compute_calibration_error(two) == pytest.approx(0.0)


def test_ece_matches_hand_computed_value_on_mixed_bins() -> None:
    records = [
        *([record(0.52, True, f"a{i}") for i in range(8)]),
        *([record(0.54, False, f"b{i}") for i in range(2)]),
        *([record(0.71, True, f"c{i}") for i in range(5)]),
        record(0.73, False, "d0"),
    ]
    # Bin 5: avg_conf=0.524, acc=0.8 -> |diff|=0.276, weight 10/16
    # Bin 7: avg_conf=(5*0.71+0.73)/6=0.7133, acc=5/6 -> |diff|=0.12, weight 6/16
    expected = (10 / 16) * abs(0.524 - 0.8) + (6 / 16) * abs((5 * 0.71 + 0.73) / 6 - 5 / 6)
    assert compute_calibration_error(records) == pytest.approx(expected, rel=1e-3)
