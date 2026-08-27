"""Tests for semantic perturbation distance and robustness budget curve (Phase 8)."""

from __future__ import annotations

import pytest

from sloplab.models.enums import Decision
from sloplab.models.evaluation import DimensionScores, EvaluationResult
from sloplab.models.run import CaseRecord
from sloplab.scoring.metrics import compute_metrics
from sloplab.scoring.perturbation import (
    compute_cosine_similarity,
    compute_robustness_perturbation_curve,
    compute_text_perturbation,
)


def test_cosine_similarity_identical_texts() -> None:
    text = "Authorization bypass vulnerability in document controller"
    assert compute_cosine_similarity(text, text) == pytest.approx(1.0)
    assert compute_text_perturbation(text, text) == pytest.approx(0.0)


def test_cosine_similarity_divergent_texts() -> None:
    text_a = "Cross-tenant access in cloud document repository"
    text_b = "Apples oranges bananas strawberries watermelon"
    sim = compute_cosine_similarity(text_a, text_b)
    dist = compute_text_perturbation(text_a, text_b)
    assert sim == pytest.approx(0.0)
    assert dist == pytest.approx(1.0)


def test_cosine_similarity_partial_overlap() -> None:
    text_a = "Missing authorization check on document lookup"
    text_b = "Missing authentication check on document lookup"
    sim = compute_cosine_similarity(text_a, text_b)
    dist = compute_text_perturbation(text_a, text_b)
    assert 0.70 < sim < 0.95
    assert 0.05 < dist < 0.30


def _make_record_with_dist(
    case_id: str,
    decision: Decision,
    expected: Decision,
    dist: float,
) -> CaseRecord:
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
        confidence=0.8,
        dimensions=DimensionScores.from_dict(dims),
    )
    rec = CaseRecord.from_result(
        res,
        case_id=case_id,
        case_kind="mutated",
        report_class="valid",
        expected_decision=expected,
    )
    rec.evaluation_metadata["perturbation_distance"] = dist
    return rec


def test_robustness_perturbation_curve_generation() -> None:
    # Bin 0 [0.0 - 0.2): dist 0.1 -> correct (1.0 acc)
    # Bin 1 [0.2 - 0.4): dist 0.3 -> correct (1.0 acc)
    # Bin 2 [0.4 - 0.6): dist 0.5 -> incorrect (0.0 acc)
    # Bin 4 [0.8 - 1.0]: dist 0.9 -> incorrect (0.0 acc)
    records = [
        _make_record_with_dist("c1", Decision.ACCEPT, Decision.ACCEPT, 0.1),
        _make_record_with_dist("c2", Decision.ACCEPT, Decision.ACCEPT, 0.3),
        _make_record_with_dist("c3", Decision.REJECT, Decision.ACCEPT, 0.5),
        _make_record_with_dist("c4", Decision.REJECT, Decision.ACCEPT, 0.9),
    ]

    curve = compute_robustness_perturbation_curve(records, bins=5)
    assert len(curve) == 5

    assert curve[0]["count"] == 1
    assert curve[0]["accuracy"] == pytest.approx(1.0)

    assert curve[1]["count"] == 1
    assert curve[1]["accuracy"] == pytest.approx(1.0)

    assert curve[2]["count"] == 1
    assert curve[2]["accuracy"] == pytest.approx(0.0)

    assert curve[3]["count"] == 0
    assert curve[3]["accuracy"] is None

    assert curve[4]["count"] == 1
    assert curve[4]["accuracy"] == pytest.approx(0.0)

    bundle = compute_metrics(records, "test-eval")
    assert len(bundle.perturbation_curve) == 5
