"""E3b: evaluator exception isolation at the shared study coordination."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from sloplab.corpus.loader import discover_fixtures
from sloplab.corpus.parser import parse_report
from sloplab.evaluators.base import _EVALUATOR_REGISTRY
from sloplab.evaluators.llm.failures import EvaluationFailure
from sloplab.models.enums import Decision
from sloplab.models.evaluation import DimensionScores, EvaluationResult
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import materialize_suite
from sloplab.scoring.harness import (
    SuiteCase,
    build_cases,
    run_case_outcome,
    run_suite,
    run_suite_with_outcomes,
)
from tests._helpers import write_canonical_fixture

_DIMS = {
    "reproducibility": 0.7,
    "evidence_completeness": 0.7,
    "claim_evidence_consistency": 0.7,
    "impact_calibration": 0.7,
    "scope_consistency": 0.7,
}


def _result(case_id: str) -> EvaluationResult:
    return EvaluationResult(
        evaluator_name="flaky-double",
        evaluator_version="0",
        case_id=case_id,
        decision=Decision.ACCEPT,
        confidence=0.8,
        dimensions=DimensionScores.from_dict(dict(_DIMS)),
        findings=[],
        rationale="ok",
        metadata={},
    )


class _FlakyEvaluator:
    """Fails the 2nd evaluation with an expected operational failure."""

    name = "flaky-double"
    version = "0"

    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, report: Any, context: Any) -> EvaluationResult:
        self.calls += 1
        _ = (report, context)
        if self.calls == 2:
            raise EvaluationFailure(
                error_kind="timeout",
                adapter_attempts=1,
                rendered_prompt_hash="abc",
                detail="transport.timeout",
            )
        return _result(context.case_id if hasattr(context, "case_id") else "x")


class _BrokenEvaluator:
    """Unexpected program error: must propagate, never isolate."""

    name = "broken-double"
    version = "0"

    def evaluate(self, report: Any, context: Any) -> Any:
        _ = (report, context)
        raise RuntimeError("simulated programming error")


def _direct_cases() -> list[SuiteCase]:
    doc = parse_report("# T\n\n## Summary\n\nBody.\n", fixture_id="x", path="x")
    return [
        SuiteCase(
            case_id=f"c-{i}",
            kind="canonical",
            parent_id=None,
            operator=None,
            report_class="valid",
            expected_decision="accept",
            expected_dimensions=dict(_DIMS),
            seed=None,
            fixture_dir=None,
            canonical_fixture=None,
            report=doc,
        )
        for i in range(3)
    ]


def test_expected_failure_is_outcome_not_record() -> None:
    records, failed = run_suite_with_outcomes(_FlakyEvaluator(), _direct_cases())
    assert len(records) == 2
    assert len(failed) == 1
    outcome = failed[0]
    assert outcome.status == "failed"
    assert outcome.record is None
    assert outcome.failure is not None
    assert outcome.failure.error_kind == "timeout"
    assert outcome.case_id == "c-1"
    assert {r.case_id for r in records} == {"c-0", "c-2"}


def test_unexpected_error_propagates() -> None:
    with pytest.raises(RuntimeError, match="simulated programming error"):
        run_suite_with_outcomes(_BrokenEvaluator(), _direct_cases())
    with pytest.raises(RuntimeError, match="simulated programming error"):
        run_case_outcome(_BrokenEvaluator(), _direct_cases()[0])


def test_strict_run_suite_still_raises() -> None:
    """The legacy strict variant propagates operational failures (unchanged)."""
    with pytest.raises(EvaluationFailure, match="timeout"):
        run_suite(_FlakyEvaluator(), _direct_cases())


def _study_workspace(tmp_path: Path) -> dict[str, Any]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Isolation clean report",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "b-000",
        fixture_id="canonical-b-000",
        title="Isolation second report",
        report_class="valid",
    )
    suite = {
        "name": "isolation-suite",
        "base_seed": 21,
        "corpus_root": str(corpus),
        "include_canonical_cases": True,
        "policies": {
            "valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]},
        },
    }
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(yaml.safe_dump(suite), encoding="utf-8")
    suite_config = SuiteConfig.model_validate(
        yaml.safe_load(suite_path.read_text(encoding="utf-8"))
    )
    canonical, _ = discover_fixtures(corpus)
    out_root = tmp_path / "out"
    materialize_suite(suite_config, canonical, out_root)
    cases = build_cases(out_root / "suite-index.jsonl", corpus, out_root)
    return {"corpus": corpus, "out": out_root, "cases": cases}


def test_study_isolates_failing_evaluator(tmp_path: Path) -> None:
    import json

    from sloplab.experiments.runner import load_study_config
    from sloplab.experiments.study import run_deterministic_study

    paths = _study_workspace(tmp_path)
    study_path = tmp_path / "study.yaml"
    study_path.write_text(
        yaml.safe_dump(
            {
                "name": "isolation-study",
                "suite": {
                    "config_path": str(tmp_path / "suite.yaml"),
                    "corpus_root": str(paths["corpus"]),
                },
                "base_seed": 21,
                "evaluators": [{"name": "e3b-flaky-double"}],
            }
        ),
        encoding="utf-8",
    )
    evaluator = _FlakyEvaluator()
    evaluator.name = "e3b-flaky-double"
    _EVALUATOR_REGISTRY["e3b-flaky-double"] = evaluator
    try:
        result = run_deterministic_study(
            load_study_config(study_path), study_path, tmp_path / "run"
        )
    finally:
        del _EVALUATOR_REGISTRY["e3b-flaky-double"]
    outcomes_path = tmp_path / "run" / "outcomes.jsonl"
    assert outcomes_path.is_file()
    rows = [
        json.loads(line)
        for line in outcomes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["error_kind"] == "timeout"
    assert rows[0]["evaluator_name"] == "e3b-flaky-double"
    records = [
        json.loads(line)
        for line in result.records_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) == len(paths["cases"]) - 1
    assert rows[0]["case_id"] not in {r["case_id"] for r in records}


def test_benchmark_isolates_and_reports_failures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import sloplab.cli.main as cli_module

    paths = _study_workspace(tmp_path)
    evaluator = _FlakyEvaluator()
    evaluator.name = "e3b-bench-double"
    _EVALUATOR_REGISTRY["e3b-bench-double"] = evaluator
    try:
        bundles = cli_module._run_evaluators_over_suite(
            ("e3b-bench-double",),
            paths["out"] / "suite-index.jsonl",
            paths["corpus"],
            paths["out"],
            tmp_path / "bench-out",
            "isolation-bench",
            21,
        )
    finally:
        del _EVALUATOR_REGISTRY["e3b-bench-double"]
    assert len(bundles) == 1
    assert bundles[0].total_cases == len(paths["cases"]) - 1
    assert "FAILED-EVAL (timeout)" in capsys.readouterr().err
    assert (tmp_path / "bench-out" / "run.jsonl").is_file()
