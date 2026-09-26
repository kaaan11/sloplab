"""Regression tests for deterministic-study reruns and provenance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

import sloplab.experiments.study as study_module
from sloplab.evaluators.llm.failures import EvaluationFailure
from sloplab.experiments.config import DeterministicStudyConfig
from sloplab.experiments.study import run_deterministic_study
from sloplab.scoring.harness import CaseOutcome
from tests._helpers import write_canonical_fixture


def _workspace(tmp_path: Path) -> tuple[DeterministicStudyConfig, Path]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "study-000",
        fixture_id="canonical-study-000",
        title="Study provenance report",
        report_class="valid",
    )
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        yaml.safe_dump(
            {
                "name": "study-provenance-suite",
                "base_seed": 23,
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
                "name": "study-provenance",
                "suite": {
                    "config_path": str(suite_path),
                    "corpus_root": str(corpus),
                },
                "base_seed": 23,
                "evaluators": [{"name": "rules-baseline"}],
            }
        ),
        encoding="utf-8",
    )
    config = DeterministicStudyConfig.model_validate(
        yaml.safe_load(study_path.read_text(encoding="utf-8"))
    )
    return config, study_path


def test_successful_rerun_removes_stale_outcomes(tmp_path: Path) -> None:
    config, study_path = _workspace(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    stale = out / "outcomes.jsonl"
    stale.write_text(
        '{"schema_version":1,"status":"failed","case_id":"stale"}\n',
        encoding="utf-8",
    )

    run_deterministic_study(config, study_path, out)

    assert not stale.exists()
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["error_count"] == 0


def test_provenance_timestamps_bracket_evaluation(tmp_path: Path, monkeypatch: Any) -> None:
    config, study_path = _workspace(tmp_path)
    calls: list[str] = []

    def _clock() -> str:
        value = "2026-09-26T10:00:00+00:00" if not calls else "2026-09-26T10:00:05+00:00"
        calls.append(value)
        return value

    real_run = study_module.run_suite_with_outcomes

    def _checked_run(*args: Any, **kwargs: Any) -> Any:
        assert calls == ["2026-09-26T10:00:00+00:00"]
        return real_run(*args, **kwargs)

    monkeypatch.setattr(study_module, "utc_now_iso", _clock)
    monkeypatch.setattr(study_module, "run_suite_with_outcomes", _checked_run)

    out = tmp_path / "out"
    run_deterministic_study(config, study_path, out)

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["started_at"] == "2026-09-26T10:00:00+00:00"
    assert manifest["finished_at"] == "2026-09-26T10:00:05+00:00"
    assert calls == [
        "2026-09-26T10:00:00+00:00",
        "2026-09-26T10:00:05+00:00",
    ]


def test_provenance_error_count_matches_failed_outcomes(tmp_path: Path, monkeypatch: Any) -> None:
    config, study_path = _workspace(tmp_path)

    def _all_fail(evaluator: Any, cases: list[Any]) -> tuple[list[Any], list[CaseOutcome]]:
        return (
            [],
            [
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
            ],
        )

    monkeypatch.setattr(study_module, "run_suite_with_outcomes", _all_fail)

    out = tmp_path / "out"
    run_deterministic_study(config, study_path, out)

    outcomes = [
        json.loads(line)
        for line in (out / "outcomes.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert len(outcomes) > 0
    assert manifest["error_count"] == len(outcomes)
