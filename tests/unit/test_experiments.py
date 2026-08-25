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
        run_a = run_deterministic_study(config, study_workspace, suite_yaml, out_a)
        run_b = run_deterministic_study(config, study_workspace, suite_yaml, out_b)

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
            config, study_workspace, study_workspace / "suite.yaml", study_workspace / "out"
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
