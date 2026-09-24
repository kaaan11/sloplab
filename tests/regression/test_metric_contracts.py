"""E4a: metric contracts — paired susceptibility and ECE counterexamples."""

from __future__ import annotations

import pytest

from sloplab.models.enums import Decision
from sloplab.models.evaluation import DimensionScores, EvaluationResult
from sloplab.models.run import CaseRecord
from sloplab.scoring.metrics import (
    compute_calibration_error,
    compute_metrics,
    compute_presentation_susceptibility,
)

_DIMS = {
    "reproducibility": 0.9,
    "evidence_completeness": 0.9,
    "claim_evidence_consistency": 0.9,
    "impact_calibration": 0.9,
    "scope_consistency": 0.9,
}


def record(
    case_id: str,
    *,
    kind: str = "canonical",
    parent_id: str | None = None,
    operator: str | None = None,
    report_class: str = "valid",
    expected: Decision | None = Decision.ACCEPT,
    decision: Decision = Decision.ACCEPT,
    confidence: float = 0.9,
) -> CaseRecord:
    result = EvaluationResult(
        evaluator_name="t",
        evaluator_version="0",
        case_id=case_id,
        decision=decision,
        confidence=confidence,
        dimensions=DimensionScores.from_dict(dict(_DIMS)),
    )
    return CaseRecord.from_result(
        result,
        case_id=case_id,
        case_kind=kind,  # type: ignore[arg-type]
        report_class=report_class,
        expected_decision=expected,
        parent_id=parent_id,
        operator=operator,
    )


def test_paired_susceptibility_zero_when_every_pair_agrees() -> None:
    """E4a counterexample 1: equal decisions per pair must give 0.

    Parent A (broken, accepted) has one accepting child; parent B (broken,
    rejected) has three rejecting children. Every pair agrees, so the paired
    metric is 0 even though group acceptance rates differ (1/2 vs 1/4).
    """
    records = [
        record("A", expected=Decision.REJECT, decision=Decision.ACCEPT),
        record(
            "a1",
            kind="mutated",
            parent_id="A",
            operator="professionalize_language",
            expected=Decision.REJECT,
            decision=Decision.ACCEPT,
        ),
        record("B", expected=Decision.REJECT, decision=Decision.REJECT),
        *(
            record(
                f"b{i}",
                kind="mutated",
                parent_id="B",
                operator="professionalize_language",
                expected=Decision.REJECT,
                decision=Decision.REJECT,
            )
            for i in range(3)
        ),
    ]
    assert compute_presentation_susceptibility(records) == 0.0


def test_parent_pairing_is_scoped_to_evaluator_repeat() -> None:
    """Reviewer counterexample: repeats must never borrow another parent decision."""
    parent_0 = record("p", expected=Decision.REJECT, decision=Decision.ACCEPT)
    child_0 = record(
        "c",
        kind="mutated",
        parent_id="p",
        operator="professionalize_language",
        expected=Decision.REJECT,
        decision=Decision.ACCEPT,
    )
    parent_1 = record("p", expected=Decision.REJECT, decision=Decision.REJECT)
    child_1 = record(
        "c",
        kind="mutated",
        parent_id="p",
        operator="professionalize_language",
        expected=Decision.REJECT,
        decision=Decision.REJECT,
    )
    for item in (parent_0, child_0):
        item.evaluation_metadata["repeat_index"] = 0
    for item in (parent_1, child_1):
        item.evaluation_metadata["repeat_index"] = 1

    records = [parent_0, child_0, parent_1, child_1]
    assert compute_presentation_susceptibility(records) == 0.0
    bundle = compute_metrics(records, "t")
    assert bundle.metric_coverage["presentation_susceptibility"]["pairs"] == 2


def test_ece_captures_confidence_one_alongside_bin_mates() -> None:
    """E4a counterexample 2: 0.95/right and 1.0/wrong share the last bin."""
    records = [
        record("a", decision=Decision.ACCEPT, confidence=0.95),
        record("b", expected=Decision.REJECT, decision=Decision.ACCEPT, confidence=1.0),
    ]
    assert compute_calibration_error(records) == pytest.approx(0.475)


def test_susceptibility_undefined_without_pairs_states_reason() -> None:
    """No parent/pair link: undefined with a stated reason, not a silent None."""
    lone = [
        record(
            "orphan",
            kind="mutated",
            parent_id="ghost",
            operator="professionalize_language",
            expected=Decision.REJECT,
            decision=Decision.ACCEPT,
        )
    ]
    assert compute_presentation_susceptibility(lone) is None
    bundle = compute_metrics(lone, "t")
    coverage = bundle.metric_coverage["presentation_susceptibility"]
    assert coverage["pairs"] == 0
    assert coverage["pairs_unresolved"] == 1
    assert coverage["children_considered"] == 1
    reason = coverage["undefined_reason"]
    assert isinstance(reason, str)
    assert "resolvable" in reason

    empty: list[CaseRecord] = []
    assert compute_presentation_susceptibility(empty) is None
    assert (
        compute_metrics(empty, "t").metric_coverage["presentation_susceptibility"][
            "undefined_reason"
        ]
        is not None
    )


def test_partition_and_range_accounting_in_coverage() -> None:
    """Every in-range record joins exactly one bin; outliers are counted."""
    records = [
        record("a", decision=Decision.ACCEPT, confidence=0.95),
        record("b", expected=Decision.REJECT, decision=Decision.ACCEPT, confidence=1.0),
    ]
    coverage = compute_metrics(records, "t").metric_coverage["calibration_error"]
    assert coverage["observations"] == 2
    assert coverage["binned"] == 2
    assert coverage["out_of_range_excluded"] == 0
    assert coverage["undefined_reason"] is None

    wild = record("w", decision=Decision.ACCEPT)
    object.__setattr__(wild, "confidence", 1.5)  # bypass model range guard
    coverage2 = compute_metrics([wild], "t").metric_coverage["calibration_error"]
    assert coverage2["observations"] == 0
    assert coverage2["out_of_range_excluded"] == 1
    assert coverage2["undefined_reason"] is not None


def _failed_record(case_id: str) -> CaseRecord:
    result = EvaluationResult(
        evaluator_name="t",
        evaluator_version="0",
        case_id=case_id,
        decision=Decision.NEEDS_MANUAL_REVIEW,
        confidence=0.5,
        dimensions=DimensionScores.from_dict(dict(_DIMS)),
        metadata={"failed": True},
    )
    return CaseRecord.from_result(
        result,
        case_id=case_id,
        case_kind="canonical",
        report_class="valid",
        expected_decision=Decision.ACCEPT,
    )


def test_failed_placeholders_never_enter_metrics() -> None:
    """Legacy failed rows are rejected at the reader boundary, not scored."""
    good = record("ok", decision=Decision.ACCEPT)
    with pytest.raises(ValueError, match="failed placeholder"):
        compute_metrics([good, _failed_record("bad")], "t")


def test_singularity_and_correct_consistency_enforced() -> None:
    """Duplicates, correct-flag drift, and dangling links raise loudly."""
    good = record("ok", decision=Decision.ACCEPT)
    with pytest.raises(ValueError, match="duplicate"):
        compute_metrics([good, record("ok", decision=Decision.ACCEPT)], "t")

    drifted = record("ok2", decision=Decision.ACCEPT)
    object.__setattr__(drifted, "correct", False)
    with pytest.raises(ValueError, match="correct"):
        compute_metrics([drifted], "t")

    dangling = record(
        "m", kind="mutated", operator="professionalize_language", expected=Decision.REJECT
    )
    with pytest.raises(ValueError, match="parent/operator"):
        compute_metrics([dangling], "t")


def test_every_metric_carries_coverage() -> None:
    """Normal bundle: all coverage entries present, defined metrics reason-free."""
    records = [
        record("p1"),
        record(
            "m1",
            kind="mutated",
            parent_id="p1",
            operator="professionalize_language",
            report_class="valid",
            expected=Decision.ACCEPT,
            decision=Decision.ACCEPT,
            confidence=0.8,
        ),
    ]
    bundle = compute_metrics(records, "t")
    expected_metrics = {
        "decision_accuracy",
        "false_reassurance",
        "over_rejection",
        "mutation_detection",
        "robustness_delta",
        "presentation_susceptibility",
        "calibration_error",
        "dimension_mae",
        "per_class_accuracy",
        "robustness_score",
    }
    assert expected_metrics <= set(bundle.metric_coverage)
    assert bundle.metric_coverage["decision_accuracy"]["scored"] == 2
    assert bundle.metric_coverage["decision_accuracy"]["unscored_no_expectation"] == 0
    for name in expected_metrics:
        assert "undefined_reason" in bundle.metric_coverage[name]
    assert bundle.metric_coverage["calibration_error"]["undefined_reason"] is None
