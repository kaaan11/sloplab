"""E1e: resolved effective recipe — recorded settings equal used settings.

Scope: frozen generation/evaluation/analysis sections and their hashes, post-
resolution mutation immunity, evaluator/order/bootstrap sensitivity, two-root
semantic stability, independent hash recomputation, and the API/CLI analysis
boundary. Full recipe/seed/config identity details live in recipe-contract.md.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.evaluators.base import get_evaluator
from sloplab.experiments.config import DeterministicStudyConfig
from sloplab.experiments.resolved_recipe import (
    evaluation_hash,
    generation_hash,
    resolve_recipe,
    settings_hash,
)
from sloplab.experiments.runner import load_study_config
from sloplab.experiments.study import run_deterministic_study
from sloplab.models.evaluation import EvaluationContext
from sloplab.models.report import ReportDocument
from sloplab.models.suite import SuiteConfig
from tests._helpers import write_canonical_fixture


def _workspace(tmp_path: Path) -> dict[str, Any]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "v-000",
        fixture_id="canonical-v-000",
        title="Recipe valid report",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "i-000",
        fixture_id="canonical-i-000",
        title="Recipe invalid report",
        report_class="invalid",
    )
    suite = {
        "name": "recipe-suite",
        "base_seed": 21,
        "corpus_root": str(corpus),
        "include_canonical_cases": True,
        "policies": {
            "valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]},
            "invalid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]},
        },
    }
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(yaml.safe_dump(suite), encoding="utf-8")
    return {"corpus": corpus, "suite": suite_path}


def _study_yaml(
    tmp_path: Path,
    suite_path: Path,
    corpus: Path,
    *,
    evaluators: list[str],
    study_seed: int = 21,
    resamples: int = 2000,
    ci: float = 0.95,
    name: str = "recipe",
) -> Path:
    payload = {
        "name": name,
        "suite": {"config_path": str(suite_path), "corpus_root": str(corpus)},
        "base_seed": study_seed,
        "evaluators": [{"name": e} for e in evaluators],
        "analysis": {"bootstrap_resamples": resamples, "bootstrap_ci": ci},
    }
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def _run(
    tmp_path: Path,
    study_path: Path,
    out_name: str,
) -> Any:
    config = load_study_config(study_path)
    return run_deterministic_study(config, study_path, tmp_path / out_name)


def _recipe_json(tmp_path: Path, out_name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        (tmp_path / out_name / "execution-recipe.json").read_text(encoding="utf-8")
    )
    return payload


def test_used_settings_equal_recorded_recipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolved objects, record provenance, and CLI bootstrap args match the recipe."""
    paths = _workspace(tmp_path)
    study_path = _study_yaml(
        tmp_path,
        paths["suite"],
        paths["corpus"],
        evaluators=["rules-baseline", "evidence-graph-baseline"],
        resamples=500,
        ci=0.99,
        name="used",
    )
    config = load_study_config(study_path)
    result = run_deterministic_study(config, study_path, tmp_path / "run")
    expected_names = ["rules-baseline", "evidence-graph-baseline"]
    assert [e.name for e in result.recipe.instances] == expected_names
    assert [e.version for e in result.recipe.instances] == [
        get_evaluator(n).version for n in expected_names
    ]
    assert [(e.name, e.version) for e in result.recipe.evaluators] == [
        (n, get_evaluator(n).version) for n in expected_names
    ]
    assert result.recipe.generation_seed == 21
    assert result.recipe.analysis is not None
    assert (result.recipe.analysis.bootstrap_resamples, result.recipe.analysis.bootstrap_ci) == (
        500,
        0.99,
    )
    records = [
        json.loads(line)
        for line in (tmp_path / "run" / "records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {(r["evaluator_name"], r["evaluator_version"]) for r in records} == {
        (n, get_evaluator(n).version) for n in expected_names
    }

    import sloplab.scoring.comparison as comparison_module

    seen: list[dict[str, Any]] = []
    real_bootstrap = comparison_module.bootstrap_accuracy_ci

    def _spy(records_arg: Any, *, resamples: int = 2000, ci: float = 0.95, seed: int = 0) -> Any:
        seen.append({"resamples": resamples, "ci": ci, "seed": seed})
        return real_bootstrap(records_arg, resamples=resamples, ci=ci, seed=seed)

    monkeypatch.setattr(comparison_module, "bootstrap_accuracy_ci", _spy)
    cli_result = CliRunner().invoke(
        cli, ["study", str(study_path), "--out", str(tmp_path / "cli-run")]
    )
    assert cli_result.exit_code == 0, cli_result.output
    assert seen
    assert all(s == {"resamples": 500, "ci": 0.99, "seed": 21} for s in seen)


def test_seed_roles_are_separate_and_generation_stable(tmp_path: Path) -> None:
    """Study seed names analysis; changing it leaves generation/records alone."""
    paths = _workspace(tmp_path)
    run_a = _study_yaml(
        tmp_path,
        paths["suite"],
        paths["corpus"],
        evaluators=["rules-baseline"],
        study_seed=99,
        name="seed-a",
    )
    run_b = _study_yaml(
        tmp_path,
        paths["suite"],
        paths["corpus"],
        evaluators=["rules-baseline"],
        study_seed=100,
        name="seed-b",
    )
    config_a = load_study_config(run_a)
    result_a = run_deterministic_study(config_a, run_a, tmp_path / "run-a")
    config_b = load_study_config(run_b)
    result_b = run_deterministic_study(config_b, run_b, tmp_path / "run-b")
    assert result_a.recipe.generation_seed == result_b.recipe.generation_seed == 21
    assert result_a.recipe.analysis is not None and result_b.recipe.analysis is not None
    assert result_a.recipe.analysis.bootstrap_seed == 99
    assert result_b.recipe.analysis.bootstrap_seed == 100
    recipe_a = _recipe_json(tmp_path, "run-a")
    recipe_b = _recipe_json(tmp_path, "run-b")
    assert recipe_a["generation_hash"] == recipe_b["generation_hash"]
    assert recipe_a["analysis_hash"] != recipe_b["analysis_hash"]
    assert recipe_a["settings_hash"] != recipe_b["settings_hash"]
    assert recipe_a["execution_hash"] != recipe_b["execution_hash"]
    assert (tmp_path / "run-a" / "records.jsonl").read_bytes() == (
        tmp_path / "run-b" / "records.jsonl"
    ).read_bytes()


def test_post_resolution_mutation_changes_neither_run_nor_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutating config/suite/registry after resolution cannot move this run."""
    import sloplab.evaluators.base as registry_module
    import sloplab.experiments.study as study_module

    paths = _workspace(tmp_path)
    clean_path = _study_yaml(
        tmp_path,
        paths["suite"],
        paths["corpus"],
        evaluators=["rules-baseline"],
        resamples=500,
        name="clean",
    )
    mutated_path = _study_yaml(
        tmp_path,
        paths["suite"],
        paths["corpus"],
        evaluators=["rules-baseline"],
        resamples=500,
        name="mutated",
    )
    clean_config = load_study_config(clean_path)
    run_deterministic_study(clean_config, clean_path, tmp_path / "clean")

    mutated_config: DeterministicStudyConfig = load_study_config(mutated_path)
    expected_config_hash = hashlib.sha256(
        json.dumps(mutated_config.model_dump(), sort_keys=True).encode()
    ).hexdigest()
    original_suite = SuiteConfig.model_validate(
        yaml.safe_load(paths["suite"].read_text(encoding="utf-8"))
    )
    monkeypatch.setattr(study_module, "load_suite_config", lambda _path: original_suite)

    class _Rogue:
        name = "rogue-eval"
        version = "9"

        def evaluate(self, report: ReportDocument, context: EvaluationContext) -> Any:
            raise AssertionError("must use the evaluator resolved before registry replacement")

    def _mutating_materialize(*args: Any, **kwargs: Any) -> Any:
        from sloplab.mutations.materialize import materialize_suite as real_materialize

        # Alter the loader-owned model before the materializer consumes its
        # private copy, and replace the actual selected registry entry.
        original_suite.base_seed = 12345
        original_suite.policies["valid"].operators = ["professionalize_language"]
        monkeypatch.setitem(registry_module._EVALUATOR_REGISTRY, "rules-baseline", _Rogue())
        outcome = real_materialize(*args, **kwargs)
        mutated_config.base_seed = 7777
        mutated_config.analysis.bootstrap_resamples = 700
        mutated_config.evaluators.clear()
        mutated_config.repeat_index = 99
        args[0].policies["valid"].operators = ["professionalize_language", "impact_inflation"]
        return outcome

    monkeypatch.setattr(study_module, "materialize_suite", _mutating_materialize)
    result = run_deterministic_study(mutated_config, mutated_path, tmp_path / "mutated")
    assert result.recipe.analysis is not None
    assert (result.recipe.analysis.bootstrap_seed, result.recipe.analysis.bootstrap_resamples) == (
        21,
        500,
    )
    assert [e.name for e in result.recipe.evaluators] == ["rules-baseline"]
    assert (tmp_path / "mutated" / "records.jsonl").read_bytes() == (
        tmp_path / "clean" / "records.jsonl"
    ).read_bytes()
    assert (tmp_path / "mutated" / "execution-recipe.json").read_bytes() == (
        tmp_path / "clean" / "execution-recipe.json"
    ).read_bytes()
    manifest = json.loads((tmp_path / "mutated" / "manifest.json").read_bytes())
    assert manifest["base_seed"] == 21
    assert manifest["repeat_index"] == 0
    assert manifest["config_hash"] == expected_config_hash


def test_evaluator_list_and_order_move_evaluation_hashes_only(tmp_path: Path) -> None:
    """Evaluator changes move evaluation/settings/execution; inputs stay fixed."""
    paths = _workspace(tmp_path)
    variants = {
        "one": ["rules-baseline"],
        "two": ["rules-baseline", "evidence-graph-baseline"],
        "swapped": ["evidence-graph-baseline", "rules-baseline"],
    }
    recipes = {}
    for name, evaluators in variants.items():
        study_path = _study_yaml(
            tmp_path, paths["suite"], paths["corpus"], evaluators=evaluators, name=name
        )
        _run(tmp_path, study_path, f"run-{name}")
        recipes[name] = _recipe_json(tmp_path, f"run-{name}")
    assert recipes["one"]["evaluation_hash"] != recipes["two"]["evaluation_hash"]
    assert recipes["two"]["evaluation_hash"] != recipes["swapped"]["evaluation_hash"]
    assert recipes["one"]["settings_hash"] != recipes["two"]["settings_hash"]
    assert recipes["one"]["execution_hash"] != recipes["two"]["execution_hash"]
    assert (
        recipes["one"]["inputs_hash"]
        == recipes["two"]["inputs_hash"]
        == recipes["swapped"]["inputs_hash"]
    )
    assert (
        recipes["one"]["selection_hash"]
        == recipes["two"]["selection_hash"]
        == recipes["swapped"]["selection_hash"]
    )


def test_bootstrap_change_moves_analysis_hashes_only(tmp_path: Path) -> None:
    """Bootstrap option changes move analysis/settings/execution; rest is fixed."""
    paths = _workspace(tmp_path)
    low_path = _study_yaml(
        tmp_path,
        paths["suite"],
        paths["corpus"],
        evaluators=["rules-baseline"],
        resamples=500,
        name="boot-low",
    )
    high_path = _study_yaml(
        tmp_path,
        paths["suite"],
        paths["corpus"],
        evaluators=["rules-baseline"],
        resamples=700,
        name="boot-high",
    )
    _run(tmp_path, low_path, "run-low")
    _run(tmp_path, high_path, "run-high")
    low = _recipe_json(tmp_path, "run-low")
    high = _recipe_json(tmp_path, "run-high")
    assert low["analysis_hash"] != high["analysis_hash"]
    assert low["settings_hash"] != high["settings_hash"]
    assert low["execution_hash"] != high["execution_hash"]
    assert low["generation_hash"] == high["generation_hash"]
    assert low["evaluation_hash"] == high["evaluation_hash"]
    assert low["inputs_hash"] == high["inputs_hash"]
    assert low["generation"] == high["generation"]
    assert low["evaluation"] == high["evaluation"]


def test_two_roots_same_semantics_same_hashes(tmp_path: Path) -> None:
    """Same content under different roots: same semantic hashes, own locations."""

    def _suite_file(root: Path, order: list[str]) -> Path:
        corpus = root / "corpus"
        write_canonical_fixture(
            corpus, "v-000", fixture_id="canonical-v-000", title="Root report", report_class="valid"
        )
        policies = {
            key: {"variants_per_fixture": 1, "operators": ["impact_inflation"]} for key in order
        }
        suite = {
            "name": "root-suite",
            "base_seed": 21,
            "corpus_root": str(corpus),
            "include_canonical_cases": True,
            "policies": policies,
        }
        path = root / "suite.yaml"
        path.write_text(yaml.safe_dump(suite), encoding="utf-8")
        return path

    def _resolve(order: list[str], root_name: str, operators: list[str] | None = None) -> Any:
        root = tmp_path / root_name
        suite_path = _suite_file(root, order)
        payload = yaml.safe_load(suite_path.read_text(encoding="utf-8"))
        if operators is not None:
            payload["policies"]["valid"]["operators"] = operators
        suite_config = SuiteConfig.model_validate(payload)
        study_path = _study_yaml(
            tmp_path, suite_path, root / "corpus", evaluators=["rules-baseline"], name=root_name
        )
        config = load_study_config(study_path)
        return resolve_recipe(
            config,
            suite_config,
            suite_config_path=suite_path,
            corpus_root=root / "corpus",
            study_config_dir=tmp_path,
        )

    recipe_a = _resolve(["valid", "invalid"], "root-a")
    recipe_b = _resolve(["invalid", "valid"], "root-b")
    assert generation_hash(recipe_a) == generation_hash(recipe_b)
    assert evaluation_hash(recipe_a) == evaluation_hash(recipe_b)
    assert recipe_a.locations is not None and recipe_b.locations is not None
    assert recipe_a.locations.corpus_root != recipe_b.locations.corpus_root
    assert settings_hash(
        generation_hash(recipe_a), evaluation_hash(recipe_a), "0" * 64
    ) == settings_hash(generation_hash(recipe_b), evaluation_hash(recipe_b), "0" * 64)

    recipe_c = _resolve(
        ["valid", "invalid"], "root-c", operators=["professionalize_language", "impact_inflation"]
    )
    assert generation_hash(recipe_c) != generation_hash(recipe_a)


def test_hashes_independently_recomputed(tmp_path: Path) -> None:
    """All seven hashes recomputed in-test from the contract's objects."""
    paths = _workspace(tmp_path)
    study_path = _study_yaml(
        tmp_path, paths["suite"], paths["corpus"], evaluators=["rules-baseline"]
    )
    _run(tmp_path, study_path, "run")
    recipe = _recipe_json(tmp_path, "run")

    def _tag(identity_type: str, fields: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(
                {"domain": "sloplab.recipe", "type": identity_type, "version": 1, **fields},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode()
        ).hexdigest()

    assert recipe["schema_version"] == 1
    assert recipe["generation_hash"] == _tag("generation", recipe["generation"])
    assert recipe["evaluation_hash"] == _tag("evaluation", recipe["evaluation"])
    assert recipe["analysis_hash"] == _tag("analysis", recipe["analysis"])
    assert recipe["settings_hash"] == _tag(
        "settings",
        {
            "generation_hash": recipe["generation_hash"],
            "evaluation_hash": recipe["evaluation_hash"],
            "analysis_hash": recipe["analysis_hash"],
        },
    )
    assert recipe["execution_hash"] == _tag(
        "execution",
        {
            "inputs_hash": recipe["inputs_hash"],
            "selection_hash": recipe["selection_hash"],
            "settings_hash": recipe["settings_hash"],
        },
    )
    identity = json.loads((tmp_path / "run" / "input-identity.json").read_text(encoding="utf-8"))
    assert recipe["inputs_hash"] == identity["inputs_hash"]
    assert recipe["selection_hash"] == identity["selection_hash"]


def test_direct_api_produces_no_analysis_claim(tmp_path: Path) -> None:
    """Direct API runs carry analysis options but record no completed analysis."""
    paths = _workspace(tmp_path)
    study_path = _study_yaml(
        tmp_path, paths["suite"], paths["corpus"], evaluators=["rules-baseline"]
    )
    result = _run(tmp_path, study_path, "run")
    assert not (tmp_path / "run" / "analysis.json").exists()
    recipe = _recipe_json(tmp_path, "run")
    assert set(recipe["analysis"]) == {
        "bootstrap_seed",
        "bootstrap_resamples",
        "bootstrap_ci",
        "paired_comparison",
        "error_taxonomy",
    }
    assert "completed" not in json.dumps(recipe)
    assert "produced" not in json.dumps(recipe)
    identity = json.loads((tmp_path / "run" / "input-identity.json").read_text(encoding="utf-8"))
    assert len(identity["cases"]) == result.case_count
