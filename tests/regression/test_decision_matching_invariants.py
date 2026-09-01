"""Guards for how a decision is compared to its ground-truth label.

`docs/decision-matching-audit.md` established that the comparison is exact enum
equality and should stay exact: crediting near-matches collapses the gap between
the competitive baseline and the deliberately blind negative control to zero, and
an evaluator answering `needs_manual_review` to every case would score 1.000.

The comparison is implemented **twice** - stored on the record and recomputed in
metrics - with different consumers. They agree today only because both are exact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sloplab.models.enums import Decision
from sloplab.reporting.writers import read_run_jsonl
from sloplab.scoring.metrics import decision_correct

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_RUN = REPO_ROOT / "benchmarks" / "results" / "v1-core-example" / "run.jsonl"


def test_stored_and_recomputed_correctness_agree() -> None:
    """`CaseRecord.correct` (models/run.py) vs `decision_correct` (metrics.py).

    `comparison.py` reads the stored field for paired win/loss and the bootstrap
    CI, while `metrics.py` recomputes it for accuracy and calibration. A change
    to one - a tolerance experiment, say - would silently split the two.
    """
    _meta, records = read_run_jsonl(REFERENCE_RUN)
    assert records

    disagreements = [
        (r.case_id, r.evaluator_name, r.correct, decision_correct(r))
        for r in records
        if r.correct != decision_correct(r)
    ]
    assert disagreements == [], disagreements


def test_matching_is_exact_not_ordinal() -> None:
    """No near-match credit anywhere: every pair of distinct decisions is wrong."""
    from sloplab.models.enums import DIMENSIONS
    from sloplab.models.evaluation import DimensionScores, EvaluationResult
    from sloplab.models.run import CaseRecord

    for expected in Decision:
        for actual in Decision:
            result = EvaluationResult(
                evaluator_name="probe",
                evaluator_version="0",
                case_id="case-probe",
                decision=actual,
                confidence=0.5,
                dimensions=DimensionScores.from_dict(dict.fromkeys(DIMENSIONS, 0.5)),
                findings=[],
                rationale="",
                metadata={},
            )
            record = CaseRecord.from_result(
                result,
                case_id="c-1",
                case_kind="canonical",
                report_class="valid",
                expected_decision=expected,
            )
            assert record.correct is (expected == actual), (expected, actual)
            assert decision_correct(record) is (expected == actual), (expected, actual)


def test_a_constant_deferral_evaluator_scores_poorly() -> None:
    """The property exact matching buys, pinned on the committed corpus.

    Under any near-match credit an evaluator answering `needs_manual_review` to
    everything scores 1.000, because that label is the majority class.
    """
    _meta, records = read_run_jsonl(REFERENCE_RUN)
    scored = [r for r in records if r.expected_decision is not None]
    always_defer = sum(
        1 for r in scored if r.expected_decision == Decision.NEEDS_MANUAL_REVIEW
    ) / len(scored)
    assert always_defer == pytest.approx(0.532, abs=0.01), always_defer
    assert always_defer < 0.6
