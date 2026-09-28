"""Issue #48 revision: pair-merge visibility + input validation (review fixes).

Two review findings fixed:
1. When the study publisher cannot resolve presentation pair ids (missing
   recipe locations, unreadable corpus, or a corpus without pair manifests),
   the cluster bootstrap silently falls back to per-fixture clusters. The
   cluster_bootstrap block must now record ``pair_merge`` = ``applied`` |
   ``skipped`` plus the reason, and the CLI must emit a visible stderr
   warning when the merge is skipped.
2. ``cluster_bootstrap_accuracy_ci`` must reject invalid inputs (resamples < 1,
   empty records, no clusters) with a clear ``ValueError`` instead of an
   ``IndexError`` from the percentile index.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pytest
import yaml
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.models.enums import Decision
from sloplab.models.run import CaseRecord
from sloplab.scoring.comparison import cluster_bootstrap_accuracy_ci


def _record(
    case_id: str,
    *,
    kind: Literal["canonical", "mutated"] = "canonical",
    parent_id: str | None = None,
    correct: bool = True,
    evaluator: str = "rules-baseline",
) -> CaseRecord:
    return CaseRecord(
        case_id=case_id,
        case_kind=kind,
        parent_id=parent_id,
        report_class="valid",
        expected_decision=Decision.ACCEPT,
        evaluator_name=evaluator,
        evaluator_version="0.0.0",
        decision=Decision.ACCEPT,
        confidence=0.9,
        dimensions={},
        correct=correct,
    )


# ---------------------------------------------------------------------------
# Finding 2: input validation
# ---------------------------------------------------------------------------


def test_zero_resamples_raises_value_error() -> None:
    records = [_record("canonical-a-000"), _record("canonical-a-000", correct=False)]
    with pytest.raises(ValueError, match="resamples"):
        cluster_bootstrap_accuracy_ci(records, resamples=0, seed=1)


def test_negative_resamples_raises_value_error() -> None:
    records = [_record("canonical-a-000")]
    with pytest.raises(ValueError, match="resamples"):
        cluster_bootstrap_accuracy_ci(records, resamples=-3, seed=1)


def test_empty_records_raise_value_error() -> None:
    with pytest.raises(ValueError, match="records"):
        cluster_bootstrap_accuracy_ci([], resamples=10, seed=1)


# ---------------------------------------------------------------------------
# Finding 1: pair_merge visibility in build_study_analysis
# ---------------------------------------------------------------------------


def _records_two_evaluators() -> list[CaseRecord]:
    rows: list[CaseRecord] = []
    for name in ("rules-baseline", "evidence-graph-baseline"):
        for cid in ("canonical-a-000", "canonical-b-000"):
            rows.append(_record(cid, correct=True, evaluator=name))
    return rows


def test_pair_merge_skipped_recorded_without_pair_ids() -> None:
    from sloplab.reporting.study_analysis import build_study_analysis

    document = build_study_analysis(
        _records_two_evaluators(),
        bootstrap_resamples=50,
        bootstrap_ci=0.95,
        bootstrap_seed=20260825,
        pair_ids=None,
    )
    cluster = document["cluster_bootstrap"]
    assert cluster["clusters"] == 2
    assert cluster["pair_merge"] == "skipped"


def test_pair_merge_applied_recorded_with_pair_ids() -> None:
    from sloplab.reporting.study_analysis import build_study_analysis

    document = build_study_analysis(
        _records_two_evaluators(),
        bootstrap_resamples=50,
        bootstrap_ci=0.95,
        bootstrap_seed=20260825,
        pair_ids={"canonical-a-000": "pair-001", "canonical-b-000": "pair-001"},
    )
    cluster = document["cluster_bootstrap"]
    assert cluster["clusters"] == 1
    assert cluster["pair_merge"] == "applied"


def test_pair_merge_overrides_cluster_count_field() -> None:
    """The recorded count and flag must always agree."""
    from sloplab.reporting.study_analysis import build_study_analysis

    document = build_study_analysis(
        _records_two_evaluators(),
        bootstrap_resamples=50,
        bootstrap_ci=0.95,
        bootstrap_seed=1,
        pair_ids={"canonical-a-000": "pair-001"},
    )
    cluster = document["cluster_bootstrap"]
    assert cluster["clusters"] == 2
    assert cluster["pair_merge"] == "applied"


# ---------------------------------------------------------------------------
# Finding 1: study CLI warning on stderr when the merge is skipped
# ---------------------------------------------------------------------------


def _write_workspace(tmp_path: Path, *, paired: bool) -> dict[str, Path]:
    """Tiny valid workspace. ``paired=True`` adds a second fixture sharing pair-001."""
    from tests._helpers import write_canonical_fixture

    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "v-000",
        fixture_id="canonical-v-000",
        title="Pair visibility valid report",
        report_class="valid",
        pair_id="pair-001" if paired else None,
    )
    if paired:
        write_canonical_fixture(
            corpus,
            "v-partner",
            fixture_id="canonical-v-partner",
            title="Pair partner report",
            report_class="valid",
            pair_id="pair-001",
        )
    suite = {
        "name": "pair-visibility-suite",
        "base_seed": 21,
        "corpus_root": str(corpus),
        "include_canonical_cases": True,
        "policies": {
            "valid": {"variants_per_fixture": 1, "operators": ["professionalize_language"]},
        },
    }
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(yaml.safe_dump(suite), encoding="utf-8")
    return {"corpus": corpus, "suite": suite_path}


def _study_payload(paths: dict[str, Path]) -> dict[str, Any]:
    return {
        "name": "pair-visibility-study",
        "suite": {"config_path": str(paths["suite"]), "corpus_root": str(paths["corpus"])},
        "base_seed": 21,
        "evaluators": [{"name": "rules-baseline"}],
    }


def test_cli_warns_on_stderr_when_pair_merge_skipped(tmp_path: Path) -> None:
    """Corpus without pair manifests -> merge skipped -> visible stderr warning."""
    paths = _write_workspace(tmp_path, paired=False)
    study_path = tmp_path / "study.yaml"
    study_path.write_text(yaml.safe_dump(_study_payload(paths)), encoding="utf-8")
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert result.exit_code == 0, result.output
    analysis = json.loads((out_dir / "analysis.json").read_text(encoding="utf-8"))
    cluster = analysis["cluster_bootstrap"]
    assert cluster["clusters"] == 1
    assert cluster["pair_merge"] == "skipped"
    assert "pair_merge=skipped" in result.stderr


def test_cli_records_pair_merge_applied_with_pair_manifests(tmp_path: Path) -> None:
    """Corpus WITH pair manifests -> merge applied -> no stderr warning."""
    paths = _write_workspace(tmp_path, paired=True)
    study_path = tmp_path / "study.yaml"
    study_path.write_text(yaml.safe_dump(_study_payload(paths)), encoding="utf-8")
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert result.exit_code == 0, result.output
    analysis = json.loads((out_dir / "analysis.json").read_text(encoding="utf-8"))
    cluster = analysis["cluster_bootstrap"]
    assert cluster["clusters"] == 1
    assert cluster["pair_merge"] == "applied"
    assert "pair_merge=skipped" not in result.stderr


def test_cli_warns_when_pair_ids_reading_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unreadable corpus manifests (helper degrades to {}) -> skipped warning."""
    import sloplab.scoring.comparison as comparison_module

    paths = _write_workspace(tmp_path, paired=False)
    monkeypatch.setattr(comparison_module, "_pair_ids_from_root", lambda root: {})
    study_path = tmp_path / "study.yaml"
    study_path.write_text(yaml.safe_dump(_study_payload(paths)), encoding="utf-8")
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert result.exit_code == 0, result.output
    analysis = json.loads((out_dir / "analysis.json").read_text(encoding="utf-8"))
    cluster = analysis["cluster_bootstrap"]
    assert cluster["pair_merge"] == "skipped"
    assert "pair_merge=skipped" in result.stderr
