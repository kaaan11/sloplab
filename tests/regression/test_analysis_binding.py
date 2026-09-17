"""E4b-r1: outcomes-bound coverage and re-verified metrics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.evaluators.base import _EVALUATOR_REGISTRY
from sloplab.evaluators.llm.failures import EvaluationFailure
from sloplab.experiments.bundle import verify_bundle, write_completion
from sloplab.reporting.analysis import AnalysisError, read_versioned_analysis
from tests._helpers import write_canonical_fixture


class _AlwaysFail:
    name = "e4b-r1-always-fail"
    version = "0"

    def evaluate(self, report: Any, context: Any) -> Any:
        _ = (report, context)
        raise EvaluationFailure(
            error_kind="timeout",
            adapter_attempts=1,
            rendered_prompt_hash="x",
            detail="transport.timeout",
        )


@pytest.fixture()
def failing_evaluator() -> Any:
    _EVALUATOR_REGISTRY[_AlwaysFail.name] = _AlwaysFail()
    try:
        yield
    finally:
        del _EVALUATOR_REGISTRY[_AlwaysFail.name]


def _study_dir(
    tmp_path: Path, name: str, base_seed: int = 21, evaluators: list[str] | None = None
) -> tuple[Path, Path]:
    corpus = tmp_path / name / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Binding study report",
        report_class="valid",
    )
    suite_path = tmp_path / name / "suite.yaml"
    suite_path.write_text(
        yaml.safe_dump(
            {
                "name": "binding-suite",
                "base_seed": base_seed,
                "corpus_root": str(corpus),
                "include_canonical_cases": True,
                "policies": {
                    "valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]},
                },
            }
        ),
        encoding="utf-8",
    )
    study_path = tmp_path / name / "study.yaml"
    study_path.write_text(
        yaml.safe_dump(
            {
                "name": f"binding-{name}",
                "suite": {"config_path": str(suite_path), "corpus_root": str(corpus)},
                "base_seed": base_seed,
                "evaluators": [{"name": n} for n in (evaluators or ["rules-baseline"])],
            }
        ),
        encoding="utf-8",
    )
    return study_path, tmp_path / f"{name}-run"


def _published_run(
    tmp_path: Path, name: str, base_seed: int = 21, evaluators: list[str] | None = None
) -> Path:
    study_path, out_dir = _study_dir(tmp_path, name, base_seed, evaluators)
    result = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert result.exit_code == 0, result.output
    return out_dir


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recomplete(out_dir: Path) -> None:
    write_completion(out_dir, kind="study")
    verify_bundle(out_dir, kind="study")


def _analysis_doc(out_dir: Path) -> dict[str, Any]:
    return json.loads((out_dir / "analysis-v1.json").read_text(encoding="utf-8"))


def _rewrite_analysis(out_dir: Path, document: dict[str, Any]) -> None:
    (out_dir / "analysis-v1.json").write_text(json.dumps(document), encoding="utf-8")


def test_failed_count_tamper_rejected(tmp_path: Path) -> None:
    """R1 counterexample 1: failed=999 with a fresh marker still refuses."""
    out_dir = _published_run(tmp_path, "b-failed")
    document = _analysis_doc(out_dir)
    document["coverage"]["rules-baseline"]["failed"] = 999
    _rewrite_analysis(out_dir, document)
    _recomplete(out_dir)
    with pytest.raises(AnalysisError, match="coverage mismatch"):
        read_versioned_analysis(out_dir / "analysis-v1.json")


def test_all_failed_evaluator_preserved(tmp_path: Path, failing_evaluator: Any) -> None:
    """R1 counterexample 2: zero-success evaluator stays visible, not dropped."""
    out_dir = _published_run(tmp_path, "b-allfail", evaluators=[_AlwaysFail.name])
    document = read_versioned_analysis(out_dir / "analysis-v1.json")
    assert document["evaluators"] == [_AlwaysFail.name]
    entry = document["coverage"][_AlwaysFail.name]
    assert entry["scored"] == 0
    assert entry["failed"] > 0
    assert entry["not_run"] == 0
    assert entry["scored"] + entry["failed"] == entry["planned"]
    bundle = document["bundles"][_AlwaysFail.name]
    assert bundle["total_cases"] == 0
    assert bundle["metric_coverage"]["decision_accuracy"]["scored"] == 0
    assert bundle["metric_coverage"]["presentation_susceptibility"]["undefined_reason"] is not None
    assert (out_dir / "records.jsonl").read_text(encoding="utf-8").strip() == ""


def test_embedded_metric_tamper_rejected(tmp_path: Path) -> None:
    """R1 counterexample 3: edited accuracy with a fresh marker still refuses."""
    out_dir = _published_run(tmp_path, "b-metric")
    document = _analysis_doc(out_dir)
    document["bundles"]["rules-baseline"]["decision_accuracy"] = 0.123456
    _rewrite_analysis(out_dir, document)
    _recomplete(out_dir)
    with pytest.raises(AnalysisError, match="do not match"):
        read_versioned_analysis(out_dir / "analysis-v1.json")


def test_mixed_partial_study_equations(tmp_path: Path, failing_evaluator: Any) -> None:
    """Partial failure: exact per-evaluator equations; CLI handles both."""
    out_dir = _published_run(tmp_path, "b-mixed", evaluators=["rules-baseline", _AlwaysFail.name])
    document = read_versioned_analysis(out_dir / "analysis-v1.json")
    assert sorted(document["evaluators"]) == sorted(["rules-baseline", _AlwaysFail.name])
    planned = document["coverage"]["rules-baseline"]["planned"]
    assert planned > 0
    for entry in document["coverage"].values():
        assert entry["planned"] == planned
        assert entry["not_run"] == 0
        assert entry["scored"] + entry["failed"] == planned
    assert document["coverage"]["rules-baseline"]["failed"] == 0
    assert document["coverage"][_AlwaysFail.name]["scored"] == 0
    assert CliRunner().invoke(cli, ["compare", str(out_dir)]).exit_code == 0
    out = tmp_path / "report.md"
    result = CliRunner().invoke(
        cli,
        [
            "report",
            str(out_dir / "records.jsonl"),
            "--analysis",
            str(out_dir / "analysis-v1.json"),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()


def test_outcomes_line_dropped_rejected(tmp_path: Path, failing_evaluator: Any) -> None:
    """Dropped outcomes row refuses even with a fresh marker."""
    out_dir = _published_run(tmp_path, "b-drop", evaluators=[_AlwaysFail.name])
    outcomes = out_dir / "outcomes.jsonl"
    lines = outcomes.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 1
    outcomes.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    _recomplete(out_dir)
    with pytest.raises(AnalysisError, match="mismatch|sorted, unique"):
        read_versioned_analysis(out_dir / "analysis-v1.json")


def test_outcomes_file_deleted_rejected(tmp_path: Path, failing_evaluator: Any) -> None:
    """Bound outcomes file deleted refuses."""
    out_dir = _published_run(tmp_path, "b-del", evaluators=[_AlwaysFail.name])
    (out_dir / "outcomes.jsonl").unlink()
    _recomplete(out_dir)
    with pytest.raises(AnalysisError, match="outcomes"):
        read_versioned_analysis(out_dir / "analysis-v1.json")


def test_planted_outcomes_rejected(tmp_path: Path, failing_evaluator: Any) -> None:
    """Unbound outcomes file planted into a success-only bundle refuses."""
    clean = _published_run(tmp_path, "b-clean")
    donor = _published_run(tmp_path, "b-donor", evaluators=[_AlwaysFail.name])
    (clean / "outcomes.jsonl").write_bytes((donor / "outcomes.jsonl").read_bytes())
    _recomplete(clean)
    with pytest.raises(AnalysisError, match="Unbound|unbound|outcomes"):
        read_versioned_analysis(clean / "analysis-v1.json")


def test_foreign_outcomes_rejected(tmp_path: Path, failing_evaluator: Any) -> None:
    """Another run's outcomes file refuses on hash."""
    out_a = _published_run(tmp_path, "b-for-a", evaluators=[_AlwaysFail.name])
    out_b = _published_run(tmp_path, "b-for-b", base_seed=22, evaluators=[_AlwaysFail.name])
    foreign = [json.loads(line) for line in (out_b / "outcomes.jsonl").read_text().splitlines()]
    assert foreign
    foreign[0] = dict(foreign[0])
    foreign[0]["case_id"] = "foreign-case"
    (out_a / "outcomes.jsonl").write_text(
        "\n".join(json.dumps(r) for r in foreign) + "\n", encoding="utf-8"
    )
    _recomplete(out_a)
    with pytest.raises(AnalysisError, match="hash mismatch"):
        read_versioned_analysis(out_a / "analysis-v1.json")


def _fix_outcomes_binding(out_dir: Path) -> None:
    """Rebind the envelope outcomes hash/lines to current file bytes."""
    outcomes = out_dir / "outcomes.jsonl"
    document = _analysis_doc(out_dir)
    document["outcomes"] = {
        "present": True,
        "path": "outcomes.jsonl",
        "sha256": _sha256(outcomes),
        "lines": len(
            [line for line in outcomes.read_text(encoding="utf-8").splitlines() if line.strip()]
        ),
    }
    _rewrite_analysis(out_dir, document)


def test_duplicate_failed_row_rejected(tmp_path: Path, failing_evaluator: Any) -> None:
    """Duplicated failed case with consistent counts still refuses."""
    out_dir = _published_run(tmp_path, "b-dupe", evaluators=[_AlwaysFail.name])
    outcomes = out_dir / "outcomes.jsonl"
    rows = [json.loads(line) for line in outcomes.read_text(encoding="utf-8").splitlines()]
    assert len(rows) > 1
    rows[-1] = dict(rows[0])
    outcomes.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    _fix_outcomes_binding(out_dir)
    _recomplete(out_dir)
    with pytest.raises(AnalysisError, match="duplicate"):
        read_versioned_analysis(out_dir / "analysis-v1.json")


def test_scored_failed_collision_rejected(tmp_path: Path) -> None:
    """A case both scored and failed refuses (unit level, consistent counts)."""
    import json as _json

    from sloplab.reporting.analysis import _verify_accounting

    out_dir = tmp_path / "collision"
    out_dir.mkdir()
    (out_dir / "suite-index.jsonl").write_text(
        _json.dumps({"record_type": "suite_header"})
        + "\n"
        + _json.dumps({"record_type": "suite_case", "case_id": "c1"})
        + "\n"
        + _json.dumps({"record_type": "suite_case", "case_id": "c2"})
        + "\n",
        encoding="utf-8",
    )
    analysis_path = out_dir / "analysis-v1.json"
    analysis_path.write_text("{}", encoding="utf-8")
    document = {"coverage": {"ev": {"planned": 3, "scored": 2, "failed": 1, "not_run": 0}}}
    records = [
        {"evaluator_name": "ev", "case_id": "c1"},
        {"evaluator_name": "ev", "case_id": "c2"},
    ]
    failed = [{"evaluator_name": "ev", "case_id": "c1"}]
    with pytest.raises(AnalysisError, match="scored and failed"):
        _verify_accounting(analysis_path, document, records, failed)


def test_not_run_row_rejected(tmp_path: Path, failing_evaluator: Any) -> None:
    """Study outcomes rows must be failed; not_run refuses."""
    out_dir = _published_run(tmp_path, "b-notrun", evaluators=[_AlwaysFail.name])
    outcomes = out_dir / "outcomes.jsonl"
    rows = [json.loads(line) for line in outcomes.read_text(encoding="utf-8").splitlines()]
    rows.append(
        {
            "status": "not_run",
            "case_id": rows[0]["case_id"],
            "evaluator_name": rows[0]["evaluator_name"],
            "repeat_index": 0,
            "reason": "injected",
        }
    )
    outcomes.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    _fix_outcomes_binding(out_dir)
    _recomplete(out_dir)
    with pytest.raises(AnalysisError, match="must be failed"):
        read_versioned_analysis(out_dir / "analysis-v1.json")


def test_evaluator_list_tamper_rejected(tmp_path: Path) -> None:
    """Envelope evaluator list edited refuses."""
    out_dir = _published_run(tmp_path, "b-evlist")
    document = _analysis_doc(out_dir)
    document["evaluators"] = []
    _rewrite_analysis(out_dir, document)
    _recomplete(out_dir)
    with pytest.raises(AnalysisError, match="mismatch|sorted, unique"):
        read_versioned_analysis(out_dir / "analysis-v1.json")


def test_evaluator_list_must_remain_a_sorted_unique_list(tmp_path: Path) -> None:
    """Reviewer counterexample: a mapping with the same keys is not a valid envelope list."""
    out_dir = _published_run(tmp_path, "b-ev-shape")
    document = _analysis_doc(out_dir)
    document["evaluators"] = {name: True for name in document["evaluators"]}
    _rewrite_analysis(out_dir, document)
    _recomplete(out_dir)
    with pytest.raises(AnalysisError, match="sorted, unique"):
        read_versioned_analysis(out_dir / "analysis-v1.json")


def test_planned_union_mismatch_rejected(tmp_path: Path) -> None:
    """Records from another selection refuse against the suite index."""
    out_a = _published_run(tmp_path, "b-union-a", base_seed=21)
    out_b = _published_run(tmp_path, "b-union-b", base_seed=22)
    assert (out_a / "records.jsonl").read_bytes() != (out_b / "records.jsonl").read_bytes()
    (out_a / "records.jsonl").write_bytes((out_b / "records.jsonl").read_bytes())
    _recomplete(out_a)
    with pytest.raises(AnalysisError, match="hash mismatch|union"):
        read_versioned_analysis(out_a / "analysis-v1.json")
