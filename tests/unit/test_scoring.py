"""Tests for scoring metrics and output writers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from sloplab.models.enums import Decision
from sloplab.models.run import CaseRecord
from sloplab.reporting.writers import (
    default_run_metadata,
    read_run_jsonl,
    write_markdown_report,
    write_records_csv,
    write_run_jsonl,
)
from sloplab.scoring.metrics import compute_metrics


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
    dims: dict[str, float] | None = None,
) -> CaseRecord:
    base_dims = {
        "reproducibility": 0.9,
        "evidence_completeness": 0.9,
        "claim_evidence_consistency": 0.9,
        "impact_calibration": 0.9,
        "scope_consistency": 0.9,
    }
    if dims:
        base_dims.update(dims)
    return CaseRecord.from_result(
        _result(case_id, decision, confidence, base_dims),
        case_id=case_id,
        case_kind=kind,  # type: ignore[arg-type]
        report_class=report_class,
        expected_decision=expected,
        parent_id=parent_id,
        operator=operator,
        expected_dimensions={"reproducibility": 0.95} if kind == "mutated" else {},
    )


def _result(
    case_id: str,
    decision: Decision,
    confidence: float,
    dims: dict[str, float],
) -> "object":  # EvaluationResult; quoted to keep helper signature simple
    from sloplab.models.evaluation import DimensionScores, EvaluationResult

    return EvaluationResult(
        evaluator_name="test-eval",
        evaluator_version="0.1.0",
        case_id=case_id,
        decision=decision,
        confidence=confidence,
        dimensions=DimensionScores.from_dict(dims),
    )


class TestMetrics:
    def test_accuracy_far_orr(self) -> None:
        records = [
            record("a", decision=Decision.ACCEPT),  # correct accept
            record(
                "b", report_class="invalid", expected=Decision.REJECT, decision=Decision.ACCEPT
            ),  # false reassurance
            record(
                "c",
                report_class="review",
                expected=Decision.NEEDS_MANUAL_REVIEW,
                decision=Decision.NEEDS_MANUAL_REVIEW,
            ),
            record("d", decision=Decision.REJECT),  # over-rejection
        ]
        bundle = compute_metrics(records, "t")
        assert bundle.decision_accuracy == 0.5
        assert bundle.false_reassurance_rate == 0.5  # accepted 1 of 2 non-accept cases
        assert bundle.over_rejection_rate == 0.5  # rejected 1 of 2 accept-expected cases

    def test_mutation_detection(self) -> None:
        records = [
            record("p1"),  # canonical valid -> accept
            record(
                "m1",
                kind="mutated",
                parent_id="p1",
                operator="remove_reproduction_step",
                report_class="valid",
                expected=Decision.NEEDS_MANUAL_REVIEW,
                decision=Decision.NEEDS_MANUAL_REVIEW,
            ),  # detected
            record(
                "m2",
                kind="mutated",
                parent_id="p2",
                operator="professionalize_language",
                report_class="valid",
                expected=Decision.ACCEPT,
                decision=Decision.REJECT,
            ),  # not counted: not degrading
        ]
        bundle = compute_metrics(records, "t")
        assert bundle.mutation_detection_rate == 1.0
        assert bundle.mutation_detection_total == 1

    def test_robustness_delta_is_drift_on_neutral_mutations(self) -> None:
        records = [
            record("p1"),
            # neutral mutation (same class expectation): drifts to review
            record(
                "n1",
                kind="mutated",
                parent_id="p1",
                operator="professionalize_language",
                report_class="valid",
                expected=Decision.ACCEPT,
                decision=Decision.NEEDS_MANUAL_REVIEW,
            ),
            record("p2"),
            # degrading mutation: excluded from drift metric
            record(
                "g1",
                kind="mutated",
                parent_id="p2",
                operator="impact_inflation",
                report_class="valid",
                expected=Decision.NEEDS_MANUAL_REVIEW,
                decision=Decision.NEEDS_MANUAL_REVIEW,
            ),
        ]
        bundle = compute_metrics(records, "t")
        assert bundle.robustness_delta == 1.0  # drifted on the only neutral comparison

    def test_presentation_susceptibility_non_accept_only(self) -> None:
        records = [
            record(
                "bad", report_class="invalid", expected=Decision.REJECT, decision=Decision.REJECT
            ),
            record(
                "bad-pol",
                kind="mutated",
                parent_id="bad",
                operator="professionalize_language",
                report_class="invalid",
                expected=Decision.REJECT,
                decision=Decision.ACCEPT,
                confidence=0.8,
            ),
        ]
        bundle = compute_metrics(records, "t")
        assert bundle.presentation_susceptibility == 1.0  # polish bought full acceptance

    def test_calibration_error_perfect_for_constant_confidence_matching_accuracy(self) -> None:
        records = [record(f"c{i}", confidence=0.75) for i in range(4)]
        bundle = compute_metrics(records, "t")
        assert bundle.calibration_error == pytest_approx(0.25)  # all correct at 0.75 conf

    def test_dimension_mae(self) -> None:
        rec = record(
            "m1",
            kind="mutated",
            parent_id="p",
            operator="op",
            report_class="valid",
            expected=Decision.NEEDS_MANUAL_REVIEW,
            decision=Decision.NEEDS_MANUAL_REVIEW,
            dims={"reproducibility": 0.85},
        )
        bundle = compute_metrics([rec], "t")
        assert bundle.dimension_mae["reproducibility"] == pytest_approx(0.10)

    def test_oracle_style_bundle_has_zero_error(self) -> None:
        recs = [
            record(
                "x1",
                confidence=1.0,
                dims={
                    d: 0.95
                    for d in (
                        "reproducibility",
                        "evidence_completeness",
                        "claim_evidence_consistency",
                        "impact_calibration",
                        "scope_consistency",
                    )
                },
            ),
            record("x2", confidence=1.0),
        ]
        for i, r in enumerate(recs):
            recs[i] = r.model_copy(update={"expected_dimensions": dict(r.dimensions)})
        bundle = compute_metrics(recs, "oracle")
        assert bundle.calibration_error == pytest_approx(0.0)
        assert all(v == 0.0 for v in bundle.dimension_mae.values())


def pytest_approx(expected: float) -> object:
    import pytest

    return pytest.approx(expected)


class TestWriters:
    def test_jsonl_round_trip(self, tmp_path: Path) -> None:
        meta = default_run_metadata(suite_name="s", base_seed=1)
        records = [
            record("a"),
            record(
                "b", decision=Decision.NEEDS_MANUAL_REVIEW, expected=Decision.NEEDS_MANUAL_REVIEW
            ),
        ]
        path = write_run_jsonl(tmp_path / "run.jsonl", meta, records)
        loaded_meta, loaded_records = read_run_jsonl(path)
        assert loaded_meta is not None and loaded_meta.suite_name == "s"
        assert len(loaded_records) == 2
        assert loaded_records[0].case_id == "a"

    def test_csv_columns(self, tmp_path: Path) -> None:
        rec = record("a")
        path = write_records_csv(tmp_path / "results.csv", [rec])
        with path.open() as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 1
        row = rows[0]
        assert row["case_id"] == "a"
        assert row["decision"] == "accept"
        assert row["correct"] == "1"
        assert "dim_reproducibility" in row

    def test_markdown_report_contains_metrics(self, tmp_path: Path) -> None:
        from sloplab.scoring.metrics import compute_metrics

        bundle = compute_metrics([record("a")], "rules-baseline")
        path = write_markdown_report(tmp_path / "report.md", [bundle], "T")
        text = path.read_text()
        assert "## Evaluator: `rules-baseline`" in text
        assert "Decision accuracy" in text


class TestRunMetadata:
    def test_metadata_fields(self) -> None:
        meta = default_run_metadata(suite_name="x", base_seed=3)
        payload = json.loads(meta.model_dump_json())
        assert payload["record_type"] == "run_metadata"
        assert payload["suite_name"] == "x"
        assert payload["base_seed"] == 3
        assert payload["python_version"]
