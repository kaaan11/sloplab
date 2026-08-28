"""Tests for multi-evaluator reporting, CSV serialization, and JSONL round-tripping."""

from __future__ import annotations

import csv
from pathlib import Path

from sloplab.models.enums import Decision
from sloplab.models.evaluation import DimensionScores, EvaluationResult
from sloplab.models.run import CaseRecord
from sloplab.reporting.writers import (
    default_run_metadata,
    read_run_jsonl,
    write_markdown_report,
    write_records_csv,
    write_run_jsonl,
)
from sloplab.scoring.metrics import MetricBundle


def _dummy_case_record(evaluator_name: str, case_id: str) -> CaseRecord:
    dims = {
        "reproducibility": 0.8,
        "evidence_completeness": 0.8,
        "claim_evidence_consistency": 0.8,
        "impact_calibration": 0.8,
        "scope_consistency": 0.8,
    }
    res = EvaluationResult(
        evaluator_name=evaluator_name,
        evaluator_version="1.0",
        case_id=case_id,
        decision=Decision.ACCEPT,
        confidence=0.85,
        dimensions=DimensionScores.from_dict(dims),
    )
    return CaseRecord.from_result(
        res,
        case_id=case_id,
        case_kind="canonical",
        report_class="valid",
        expected_decision=Decision.ACCEPT,
    )


def test_multi_evaluator_markdown_report_formatting(tmp_path: Path) -> None:
    b1 = MetricBundle(
        evaluator_name="eval-a", total_cases=10, correct_cases=8, decision_accuracy=0.8
    )
    b2 = MetricBundle(
        evaluator_name="eval-b", total_cases=10, correct_cases=9, decision_accuracy=0.9
    )
    b3 = MetricBundle(
        evaluator_name="eval-c",
        total_cases=10,
        correct_cases=10,
        decision_accuracy=1.0,
        injection_resistance_rate=0.95,
        attack_success_rate=0.05,
        injection_cases_count=5,
    )

    out_file = tmp_path / "matrix_report.md"
    write_markdown_report(out_file, [b1, b2, b3], "Tri-Evaluator Comparison")

    content = out_file.read_text(encoding="utf-8")
    assert "# Tri-Evaluator Comparison" in content
    assert "## Evaluator: `eval-a`" in content
    assert "## Evaluator: `eval-b`" in content
    assert "## Evaluator: `eval-c`" in content
    assert "Injection resistance rate (IRR): 0.950" in content
    assert "Attack success rate (ASR): 0.050" in content


def test_write_records_csv_output_structure(tmp_path: Path) -> None:
    records = [
        _dummy_case_record("eval-1", "case-1"),
        _dummy_case_record("eval-2", "case-2"),
    ]
    csv_file = tmp_path / "results.csv"
    write_records_csv(csv_file, records)

    with csv_file.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert "case_id" in header
        assert "decision" in header
        assert "correct" in header
        assert "confidence" in header
        assert any(col.startswith("dim_") for col in header)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0][0] == "case-1"
        assert rows[1][0] == "case-2"


def test_run_jsonl_roundtrip_integrity(tmp_path: Path) -> None:
    meta = default_run_metadata(suite_name="roundtrip-suite", base_seed=123)
    records = [_dummy_case_record("roundtrip-eval", f"c{i}") for i in range(3)]

    out_jsonl = tmp_path / "run.jsonl"
    write_run_jsonl(out_jsonl, meta, records)

    read_meta, read_records = read_run_jsonl(out_jsonl)
    assert read_meta is not None
    assert read_meta.suite_name == "roundtrip-suite"
    assert read_meta.base_seed == 123
    assert len(read_records) == 3
    for orig, loaded in zip(records, read_records, strict=True):
        assert orig.case_id == loaded.case_id
        assert orig.evaluator_name == loaded.evaluator_name
        assert orig.decision == loaded.decision
