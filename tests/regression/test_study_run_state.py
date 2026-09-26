"""Regression coverage for deterministic-study run-local state and provenance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import sloplab.experiments.study as study_module
from sloplab.evaluators.llm.failures import EvaluationFailure
from sloplab.experiments.runner import load_study_config
from sloplab.experiments.study import run_deterministic_study
from sloplab.scoring.harness import CaseOutcome, run_suite_with_outcomes
from tests._helpers import write_canonical_fixture


def _workspace(tmp_path: Path) -> tuple[Path, Path]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "v-000",
        fixture_id="canonical-v-000",
        title="Study state report",
        report_class="valid",
    )
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        yaml.safe_dump(
            {
                "name": "study-state-suite",
                "base_seed": 21,
                "corpus_root": str(corpus),
                "include_canonical_cases": True,
                "policies": {
                    "valid": {
                        "variants_per_fixture": 1,
                        "operators": ["impact_inflation"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    study_path = tmp_path / "study.yaml"
    study_path.write_text(
        yaml.safe_dump(
            {
                "name": "study-state",
                "suite": {
                    "config_path": str(suite_path),
                    "corpus_root": str(corpus),
                },
                "base_seed": 21,
                "evaluators": [{"name": "rules-baseline"}],
            }
        ),
        encoding="utf-8",
    )
    return study_path, tmp_path / "out"


def _failed_outcomes(evaluator: Any, cases: list[Any]) -> tuple[list[Any], list[CaseOutcome]]:
    failures = [
        CaseOutcome(
            case_id=case.case_id,
            evaluator_name=evaluator.name,
            status="failed",
            failure=EvaluationFailure(
                error_kind="timeout",
                adapter_attempts=1,
                rendered_prompt_hash="0" * 64,
                detail="transport.timeout",
            ),
        )
        for case in cases
    ]
    return [], failures


def test_reused_output_drops_stale_outcomes_after_clean_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    study_path, out_dir = _workspace(tmp_path)
    config = load_study_config(study_path)
    real_run = run_suite_with_outcomes

    monkeypatch.setattr(study_module, "run_suite_with_outcomes", _failed_outcomes)
    failed = run_deterministic_study(config, study_path, out_dir)
    outcomes_path = out_dir / "outcomes.jsonl"
    assert outcomes_path.is_file()
    rows = [
        json.loads(line)
        for line in outcomes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    failed_manifest = json.loads(failed.manifest_path.read_text(encoding="utf-8"))
    assert len(rows) == failed.case_count > 0
    assert failed_manifest["error_count"] == len(rows)

    monkeypatch.setattr(study_module, "run_suite_with_outcomes", real_run)
    clean = run_deterministic_study(config, study_path, out_dir)
    clean_manifest = json.loads(clean.manifest_path.read_text(encoding="utf-8"))

    assert not outcomes_path.exists()
    assert clean_manifest["error_count"] == 0


def test_provenance_times_bracket_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    study_path, out_dir = _workspace(tmp_path)
    config = load_study_config(study_path)
    real_run = run_suite_with_outcomes
    events: list[str] = []
    ticks = iter(
        [
            "2026-09-26T12:00:00+00:00",
            "2026-09-26T12:00:10+00:00",
        ]
    )

    def _clock() -> str:
        events.append("clock")
        return next(ticks)

    def _run(evaluator: Any, cases: list[Any]) -> Any:
        events.append("evaluate")
        return real_run(evaluator, cases)

    monkeypatch.setattr(study_module, "utc_now_iso", _clock)
    monkeypatch.setattr(study_module, "run_suite_with_outcomes", _run)

    result = run_deterministic_study(config, study_path, out_dir)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert events == ["clock", "evaluate", "clock"]
    assert manifest["started_at"] == "2026-09-26T12:00:00+00:00"
    assert manifest["finished_at"] == "2026-09-26T12:00:10+00:00"
    assert manifest["error_count"] == 0
