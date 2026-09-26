"""V24 exit criteria: deterministic studies are byte-identical for commit+seed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from sloplab.experiments.runner import load_pilot_config, load_study_config
from sloplab.experiments.study import run_deterministic_study


@pytest.fixture()
def study_workspace(tmp_path: Path, make_fixture: Any) -> Path:
    for i in range(3):
        make_fixture(
            tmp_path,
            f"val-{i:03d}",
            fixture_id=f"canonical-val-{i:03d}",
            title=f"Study valid report {i}",
            report_class="valid",
        )
    make_fixture(
        tmp_path,
        "inv-000",
        fixture_id="canonical-inv-000",
        title="Study invalid report",
        report_class="invalid",
    )
    suite = {
        "name": "study-suite",
        "base_seed": 21,
        "corpus_root": str(tmp_path),
        "include_canonical_cases": True,
        "policies": {
            "valid": {
                "variants_per_fixture": 2,
                "operators": ["impact_inflation", "professionalize_language"],
            },
            "invalid": {"variants_per_fixture": 1, "operators": ["confidence_overstatement"]},
        },
    }
    (tmp_path / "suite.yaml").write_text(yaml.safe_dump(suite), encoding="utf-8")

    study = {
        "name": "study-v24",
        "suite": {"config_path": str(tmp_path / "suite.yaml"), "corpus_root": str(tmp_path)},
        "base_seed": 21,
        "evaluators": [{"name": "rules-baseline"}, {"name": "evidence-graph-baseline"}],
    }
    (tmp_path / "study.yaml").write_text(yaml.safe_dump(study), encoding="utf-8")
    return tmp_path


class TestDeterministicStudy:
    def test_byte_identical_records_across_runs(self, study_workspace: Path) -> None:
        config = load_study_config(study_workspace / "study.yaml")
        suite_yaml = study_workspace / "suite.yaml"

        out_a = study_workspace / "runA"
        out_b = study_workspace / "runB"
        run_a = run_deterministic_study(config, suite_yaml, out_a)
        run_b = run_deterministic_study(config, suite_yaml, out_b)

        assert run_a.records_path.read_bytes() == run_b.records_path.read_bytes()
        # Derived adversarial content is also stable.
        a_files = {
            str(p.relative_to(out_a)): p.read_bytes() for p in out_a.rglob("*") if p.is_file()
        }
        b_files = {
            str(p.relative_to(out_b)): p.read_bytes() for p in out_b.rglob("*") if p.is_file()
        }
        for key in a_files:
            if key.endswith(("records.jsonl",)):
                continue  # compared explicitly above
            if key.startswith("adversarial/"):
                assert a_files[key] == b_files[key], key

    def test_manifest_carries_provenance(self, study_workspace: Path) -> None:
        config = load_study_config(study_workspace / "study.yaml")
        result = run_deterministic_study(
            config, study_workspace / "study.yaml", study_workspace / "out"
        )
        manifest = json.loads(result.manifest_path.read_text())
        assert manifest["experiment_name"] == "study-v24"
        assert manifest["base_seed"] == 21
        assert manifest["config_hash"]
        assert manifest["suite_hash"]
        assert len(manifest["evaluators"]) == 2
        assert set(manifest["evaluator_config_hashes"]) == {
            "rules-baseline",
            "evidence-graph-baseline",
        }
        assert manifest["started_at"] and manifest["finished_at"]

    def test_reused_output_drops_stale_outcomes_and_counts_failures(
        self, study_workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sloplab.experiments.study as study_module
        from sloplab.evaluators.llm.failures import EvaluationFailure
        from sloplab.scoring.harness import CaseOutcome

        config = load_study_config(study_workspace / "study.yaml")
        study_path = study_workspace / "study.yaml"
        out = study_workspace / "reused-out"
        real_run = study_module.run_suite_with_outcomes

        def _failed_run(evaluator: Any, cases: list[Any]) -> tuple[list[Any], list[CaseOutcome]]:
            case = cases[0]
            failure = EvaluationFailure(
                error_kind="timeout",
                adapter_attempts=1,
                rendered_prompt_hash="0" * 64,
                detail="transport.timeout",
            )
            return (
                [],
                [
                    CaseOutcome(
                        case_id=case.case_id,
                        evaluator_name=evaluator.name,
                        status="failed",
                        failure=failure,
                    )
                ],
            )

        monkeypatch.setattr(study_module, "run_suite_with_outcomes", _failed_run)
        first = run_deterministic_study(config, study_path, out)
        first_manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
        first_outcomes = [
            json.loads(line)
            for line in (out / "outcomes.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert first_manifest["error_count"] == len(first_outcomes) == 2

        monkeypatch.setattr(study_module, "run_suite_with_outcomes", real_run)
        second = run_deterministic_study(config, study_path, out)
        second_manifest = json.loads(second.manifest_path.read_text(encoding="utf-8"))
        assert second_manifest["error_count"] == 0
        assert not (out / "outcomes.jsonl").exists()

    def test_provenance_timestamps_bracket_evaluation(
        self, study_workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sloplab.experiments.study as study_module

        config = load_study_config(study_workspace / "study.yaml")
        study_path = study_workspace / "study.yaml"
        real_run = study_module.run_suite_with_outcomes
        clock_values = iter(["2026-01-01T00:00:00+00:00", "2026-01-01T00:00:01+00:00"])
        clock_calls: list[str] = []

        def _clock() -> str:
            value = next(clock_values)
            clock_calls.append(value)
            return value

        def _observed_run(evaluator: Any, cases: list[Any]) -> tuple[list[Any], list[Any]]:
            assert clock_calls == ["2026-01-01T00:00:00+00:00"]
            return real_run(evaluator, cases)

        monkeypatch.setattr(study_module, "utc_now_iso", _clock)
        monkeypatch.setattr(study_module, "run_suite_with_outcomes", _observed_run)

        result = run_deterministic_study(config, study_path, study_workspace / "timed-out")
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

        assert manifest["started_at"] == "2026-01-01T00:00:00+00:00"
        assert manifest["finished_at"] == "2026-01-01T00:00:01+00:00"
        assert clock_calls == [
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:01+00:00",
        ]


class TestConfigLoading:
    def test_pilot_config_loads_with_budget(self, tmp_path: Path) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        config = load_pilot_config(repo_root / "experiments/configs/llm-pilot-v0.2.yaml")
        assert config.repeats == 3
        assert config.budget.max_requests == 180

    def test_invalid_study_config_reports_field(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.safe_dump({"name": "x"}), encoding="utf-8")
        with pytest.raises(ValueError, match="suite"):
            load_study_config(path)
