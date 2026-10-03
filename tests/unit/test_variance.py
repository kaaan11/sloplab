"""Verified repeated observations: preserve failures, conditions and input identity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.experiments.bundle import begin_publish, finish_publish
from sloplab.experiments.variance import VarianceError, analyze_variance
from sloplab.models.enums import Decision
from tests.unit.test_scoring import record


def bundle(
    root: Path,
    name: str,
    *,
    model: str = "model-a",
    base_seed: int = 1,
    hash_value: str = "a" * 64,
    failure: bool = False,
) -> Path:
    path = root / name
    begin_publish(path, kind="llm-pilot")
    manifest = {
        "model_id": model,
        "prompt_hash": "template",
        "base_seed": base_seed,
        "temperature": 0,
        "output_mode": "json_schema",
    }
    records = []
    outcomes = []
    for case_id in ("a", "b"):
        for repeat in (0, 1):
            failed = failure and case_id == "a" and repeat == 1
            outcomes.append(
                {
                    "case_id": case_id,
                    "repeat_index": repeat,
                    "status": "failed" if failed else "success",
                }
            )
            if failed:
                continue
            row = record(
                case_id,
                decision=Decision.REJECT if case_id == "b" and repeat else Decision.ACCEPT,
                confidence=0.2 if repeat else 0.8,
            )
            row.evaluation_metadata.update(repeat_index=repeat, rendered_prompt_hash=hash_value)
            records.append(row.model_dump_json())
    (path / "manifest.json").write_text(json.dumps(manifest))
    (path / "records.jsonl").write_text("\n".join(records) + "\n")
    (path / "outcomes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in outcomes))
    finish_publish(path, kind="llm-pilot")
    return path


def test_variance_counts_flips_and_confidence_range(tmp_path: Path) -> None:
    report = analyze_variance([bundle(tmp_path, "one")], samples=100, seed=7)
    group = report["conditions"][0]
    assert group["eligible_cases"] == 2
    assert group["flip_rate"] == 0.5
    assert group["flip_rate_interval"] == [0.0, 1.0]
    assert group["cases"][0]["confidence_range"] == pytest.approx(0.6)
    assert group["cases"][1]["decision_counts"] == {"accept": 1, "reject": 1}


def test_failed_repeat_does_not_become_a_stable_case(tmp_path: Path) -> None:
    group = analyze_variance([bundle(tmp_path, "one", failure=True)], samples=100)["conditions"][0]
    assert group["observation_statuses"] == {"success": 3, "failed": 1}
    assert group["eligible_cases"] == 1
    assert group["flip_rate_interval"] is None
    assert group["cases"][0]["eligible_for_flip_interval"] is False


def test_duplicate_bundle_cannot_inflate_observations(tmp_path: Path) -> None:
    path = bundle(tmp_path, "one")
    with pytest.raises(VarianceError, match="more than once"):
        analyze_variance([path, path])


def test_same_case_changed_input_is_rejected(tmp_path: Path) -> None:
    first = bundle(tmp_path, "one")
    second = bundle(tmp_path, "two", hash_value="b" * 64)
    with pytest.raises(VarianceError, match="different rendered inputs"):
        analyze_variance([first, second])


def test_models_are_separate_conditions_and_seeds_remain_visible(tmp_path: Path) -> None:
    first = bundle(tmp_path, "one")
    second = bundle(tmp_path, "two", model="model-b", base_seed=2)
    report = analyze_variance([first, second])
    assert len(report["conditions"]) == 2
    assert {g["sources"][0]["base_seed"] for g in report["conditions"]} == {1, 2}


def test_presentation_pair_uses_one_bootstrap_cluster(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "sloplab.experiments.variance._pair_ids_from_root", lambda root: {"a": "pair", "b": "pair"}
    )
    group = analyze_variance([bundle(tmp_path, "one")], samples=100)["conditions"][0]
    assert group["logical_report_clusters"] == 1
    assert group["flip_rate_interval"] is None


def test_variance_cli_replays_without_network(tmp_path: Path) -> None:
    path = bundle(tmp_path, "one")
    out = tmp_path / "variance.json"
    result = CliRunner().invoke(
        cli, ["variance", str(path), "--bootstrap-samples", "100", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(out.read_text())["conditions"][0]["flip_rate"] == 0.5


def test_incomplete_bundle_is_rejected(tmp_path: Path) -> None:
    path = bundle(tmp_path, "one")
    (path / "records.jsonl").write_text("")
    with pytest.raises(VarianceError, match="hash mismatch"):
        analyze_variance([path])
