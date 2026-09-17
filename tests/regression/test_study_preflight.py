"""E1a: deterministic study preflight rejects unsupported settings before side effects.

Scope: nonempty evaluator ``config`` mappings, unknown evaluator names, and the
``analysis``/``provenance`` flags the runner records but does not apply. The
success path (including nondefault in-range bootstrap settings and differing
study/suite seeds) must keep working; E0 data equivalence is verified by the
manual single-run check in the delivery (not pinned here, so later packages that
intentionally change outputs are not blocked by a golden test).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.experiments.runner import load_study_config
from sloplab.experiments.study import StudyConfigError, run_deterministic_study


def _write_workspace(tmp_path: Path) -> dict[str, Path]:
    """Tiny valid workspace: corpus + suite file. Returns paths."""
    from tests._helpers import write_canonical_fixture

    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "v-000",
        fixture_id="canonical-v-000",
        title="Preflight valid report",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "i-000",
        fixture_id="canonical-i-000",
        title="Preflight invalid report",
        report_class="invalid",
    )
    suite = {
        "name": "preflight-suite",
        "base_seed": 21,
        "corpus_root": str(corpus),
        "include_canonical_cases": True,
        "policies": {
            "valid": {
                "variants_per_fixture": 1,
                "operators": ["professionalize_language"],
            },
            "invalid": {
                "variants_per_fixture": 1,
                "operators": ["confidence_overstatement"],
            },
        },
    }
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(yaml.safe_dump(suite), encoding="utf-8")
    return {"corpus": corpus, "suite": suite_path}


def _study_dict(
    suite_path: Path,
    corpus: Path,
    evaluators: list[dict[str, Any]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    study: dict[str, Any] = {
        "name": "preflight-study",
        "suite": {"config_path": str(suite_path), "corpus_root": str(corpus)},
        "base_seed": 21,
        "evaluators": evaluators or [{"name": "rules-baseline"}],
    }
    study.update(overrides)
    return study


def _write_study(tmp_path: Path, payload: dict[str, Any], name: str = "study.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


REJECTION_CASES: list[tuple[str, dict[str, Any], str]] = [
    (
        "nonempty-evaluator-config",
        {"evaluators": [{"name": "rules-baseline", "config": {"threshold": "s3cr3t"}}]},
        "evaluators[0].config",
    ),
    (
        "paired-comparison-false",
        {"analysis": {"paired_comparison": False}},
        "analysis.paired_comparison",
    ),
    (
        "error-taxonomy-false",
        {"analysis": {"error_taxonomy": False}},
        "analysis.error_taxonomy",
    ),
    (
        "record-commit-sha-false",
        {"provenance": {"record_commit_sha": False}},
        "provenance.record_commit_sha",
    ),
    (
        "record-suite-hash-false",
        {"provenance": {"record_suite_hash": False}},
        "provenance.record_suite_hash",
    ),
    (
        "record-evaluator-config-hash-false",
        {"provenance": {"record_evaluator_config_hash": False}},
        "provenance.record_evaluator_config_hash",
    ),
]


@pytest.mark.parametrize(("case_id", "study_override", "field"), REJECTION_CASES)
def test_unsupported_setting_rejected_before_side_effects(
    tmp_path: Path, case_id: str, study_override: dict[str, Any], field: str
) -> None:
    """Each unsupported setting fails preflight; no output directory is created."""
    paths = _write_workspace(tmp_path)
    payload = _study_dict(paths["suite"], paths["corpus"], **study_override)
    config = load_study_config(_write_study(tmp_path, payload))
    out_dir = tmp_path / "out"
    with pytest.raises(StudyConfigError, match=re.escape(field)):
        run_deterministic_study(config, tmp_path / "study.yaml", out_dir)
    assert not out_dir.exists(), case_id


def test_nonempty_evaluator_config_names_evaluator_and_hides_values(tmp_path: Path) -> None:
    """The error names the evaluator and field but does not echo config values."""
    paths = _write_workspace(tmp_path)
    payload = _study_dict(
        paths["suite"],
        paths["corpus"],
        evaluators=[{"name": "rules-baseline", "config": {"threshold": "s3cr3t"}}],
    )
    config = load_study_config(_write_study(tmp_path, payload))
    with pytest.raises(StudyConfigError) as exc_info:
        run_deterministic_study(config, tmp_path / "study.yaml", tmp_path / "out")
    message = str(exc_info.value)
    assert "rules-baseline" in message
    assert "evaluators[0].config" in message
    assert "s3cr3t" not in message


def test_unknown_evaluator_last_runs_nothing_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even a trailing unknown name stops the run before materialization/evaluation."""
    import sloplab.experiments.study as study_module

    calls: list[str] = []

    def _fail_materialize(*args: Any, **kwargs: Any) -> Any:
        calls.append("materialize_suite")

    def _fail_run_suite(*args: Any, **kwargs: Any) -> Any:
        calls.append("run_suite_with_outcomes")

    monkeypatch.setattr(study_module, "materialize_suite", _fail_materialize)
    monkeypatch.setattr(study_module, "run_suite_with_outcomes", _fail_run_suite)
    paths = _write_workspace(tmp_path)
    payload = _study_dict(
        paths["suite"],
        paths["corpus"],
        evaluators=[{"name": "rules-baseline"}, {"name": "no-such-evaluator"}],
    )
    config = load_study_config(_write_study(tmp_path, payload))
    out_dir = tmp_path / "out"
    with pytest.raises(StudyConfigError, match="no-such-evaluator"):
        run_deterministic_study(config, tmp_path / "study.yaml", out_dir)
    assert calls == []
    assert not out_dir.exists()


def test_failed_run_leaves_existing_output_dir_untouched(tmp_path: Path) -> None:
    """A pre-existing output dir with a sentinel keeps exactly that file."""
    paths = _write_workspace(tmp_path)
    payload = _study_dict(
        paths["suite"],
        paths["corpus"],
        evaluators=[{"name": "rules-baseline", "config": {"x": "y"}}],
    )
    config = load_study_config(_write_study(tmp_path, payload))
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    sentinel = out_dir / "sentinel.txt"
    sentinel.write_text("do not touch", encoding="utf-8")
    with pytest.raises(StudyConfigError):
        run_deterministic_study(config, tmp_path / "study.yaml", out_dir)
    assert [p.name for p in sorted(out_dir.iterdir())] == ["sentinel.txt"]
    assert sentinel.read_text(encoding="utf-8") == "do not touch"


def test_default_and_supported_nondefault_settings_accepted(tmp_path: Path) -> None:
    """Empty configs, defaults, nondefault in-range bootstrap, and split seeds run."""
    paths = _write_workspace(tmp_path)
    payload = _study_dict(
        paths["suite"],
        paths["corpus"],
        evaluators=[{"name": "rules-baseline"}, {"name": "evidence-graph-baseline"}],
        base_seed=99,
        analysis={"bootstrap_resamples": 500, "bootstrap_ci": 0.99},
    )
    config = load_study_config(_write_study(tmp_path, payload))
    result = run_deterministic_study(config, tmp_path / "study.yaml", tmp_path / "out")
    assert result.case_count > 0
    assert result.records_path.is_file()


def test_cli_rejects_unknown_evaluator_without_traceback(tmp_path: Path) -> None:
    """CLI error path: nonzero exit, readable message, no traceback, no output dir."""
    paths = _write_workspace(tmp_path)
    payload = _study_dict(
        paths["suite"],
        paths["corpus"],
        evaluators=[{"name": "rules-baseline"}, {"name": "no-such-evaluator"}],
    )
    study_path = _write_study(tmp_path, payload)
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert result.exit_code == 1
    # Clean Click-handled exit (SystemExit), not a leaked program error: an
    # unhandled ValueError would surface here as result.exception instead.
    assert isinstance(result.exception, SystemExit)
    assert "no-such-evaluator" in result.output
    assert "Traceback" not in result.output
    assert not out_dir.exists()


def test_cli_rejects_unsupported_flag_without_traceback(tmp_path: Path) -> None:
    """CLI error path for a provenance flag; pre-existing out dir stays intact."""
    paths = _write_workspace(tmp_path)
    payload = _study_dict(
        paths["suite"],
        paths["corpus"],
        provenance={"record_suite_hash": False},
    )
    study_path = _write_study(tmp_path, payload)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    sentinel = out_dir / "sentinel.txt"
    sentinel.write_text("do not touch", encoding="utf-8")
    result = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "provenance.record_suite_hash" in result.output
    assert "Traceback" not in result.output
    assert [p.name for p in sorted(out_dir.iterdir())] == ["sentinel.txt"]


def test_cli_accepts_supported_study(tmp_path: Path) -> None:
    """CLI success path still works through the new preflight."""
    paths = _write_workspace(tmp_path)
    payload = _study_dict(paths["suite"], paths["corpus"])
    study_path = _write_study(tmp_path, payload)
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert result.exit_code == 0, result.output
    assert (out_dir / "records.jsonl").is_file()
