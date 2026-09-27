"""Issue #59: no delete-before-write in `benchmark` and `study` reruns.

A rerun must validate and produce first, publish new files atomically, and
only then clean stale outputs. An interrupted rerun (broken corpus config,
crash, forced error) must leave the previous good results byte-identical.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.experiments.config import DeterministicStudyConfig
from tests._helpers import write_canonical_fixture


def _benchmark_workspace(tmp_path: Path, make_fixture: Any) -> Path:
    make_fixture(
        tmp_path,
        "val-000",
        fixture_id="canonical-val-000",
        title="Issue 59 valid report",
        report_class="valid",
    )
    suite = {
        "name": "issue59-suite",
        "base_seed": 11,
        "corpus_root": str(tmp_path),
        "include_canonical_cases": True,
        "policies": {
            "valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]},
        },
    }
    (tmp_path / "suite.yaml").write_text(yaml.safe_dump(suite), encoding="utf-8")
    return tmp_path


def _snapshot(out_dir: Path) -> dict[str, bytes]:
    return {
        p.relative_to(out_dir).as_posix(): p.read_bytes()
        for p in sorted(out_dir.rglob("*"))
        if p.is_file()
    }


def test_benchmark_broken_corpus_keeps_previous_results(tmp_path: Path, make_fixture: Any) -> None:
    """Broken corpus config on rerun fails AND leaves previous files identical."""
    workspace = _benchmark_workspace(tmp_path, make_fixture)
    out_dir = workspace / "results"
    runner = CliRunner()
    first = runner.invoke(
        cli,
        [
            "benchmark",
            str(workspace / "suite.yaml"),
            "--evaluator",
            "rules-baseline",
            "--out",
            str(out_dir),
        ],
    )
    assert first.exit_code == 0, first.output
    assert (out_dir / "run.jsonl").is_file()
    assert (out_dir / "results.csv").is_file()
    assert (out_dir / "report.md").is_file()
    assert list(out_dir.glob("metrics-*.json"))
    before = _snapshot(out_dir)

    broken_suite = workspace / "suite-broken.yaml"
    broken_suite.write_text(
        yaml.safe_dump(
            {
                "name": "issue59-suite",
                "base_seed": 11,
                "corpus_root": str(workspace / "does-not-exist"),
                "include_canonical_cases": True,
                "policies": {
                    "valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]},
                },
            }
        ),
        encoding="utf-8",
    )
    second = runner.invoke(
        cli,
        [
            "benchmark",
            str(broken_suite),
            "--evaluator",
            "rules-baseline",
            "--out",
            str(out_dir),
        ],
    )

    assert second.exit_code != 0
    assert _snapshot(out_dir) == before


def _study_workspace(tmp_path: Path) -> tuple[Any, Path]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "study-000",
        fixture_id="canonical-study-000",
        title="Issue 59 study report",
        report_class="valid",
    )
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        yaml.safe_dump(
            {
                "name": "issue59-study-suite",
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
                "name": "issue59-study",
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


def test_study_failure_before_evaluation_keeps_previous_outcomes(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Forced failure before evaluation leaves the previous outcomes.jsonl intact."""
    import sloplab.experiments.study as study_module
    from sloplab.experiments.study import run_deterministic_study

    config, study_path = _study_workspace(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    previous = (
        json.dumps(
            {
                "schema_version": 1,
                "status": "failed",
                "case_id": "previous-good-row",
                "evaluator_name": "rules-baseline",
                "repeat_index": 0,
                "error_kind": "timeout",
                "adapter_attempts": 1,
                "rendered_prompt_hash": "A" * 64,
                "detail": "transport.timeout",
            },
            sort_keys=True,
        )
        + "\n"
    )
    (out / "outcomes.jsonl").write_text(previous, encoding="utf-8")

    def _broken(*args: Any, **kwargs: Any) -> Any:
        raise ValueError("simulated broken corpus before evaluation")

    monkeypatch.setattr(study_module, "discover_fixtures", _broken)

    with pytest.raises(ValueError, match="simulated broken corpus"):
        run_deterministic_study(config, study_path, out)

    assert (out / "outcomes.jsonl").read_text(encoding="utf-8") == previous
