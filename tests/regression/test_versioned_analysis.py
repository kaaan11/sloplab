"""E4b: versioned analysis publication bound to verified metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.experiments.bundle import verify_bundle, write_completion
from sloplab.reporting.analysis import (
    ANALYSIS_DEFINITION_VERSION,
    AnalysisError,
    analysis_filename,
    read_versioned_analysis,
    write_versioned_analysis,
)
from tests._helpers import write_canonical_fixture


def _study_dir(tmp_path: Path, name: str, base_seed: int = 21) -> tuple[Path, Path]:
    corpus = tmp_path / name / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Versioned analysis report",
        report_class="valid",
    )
    suite_path = tmp_path / name / "suite.yaml"
    suite_path.write_text(
        yaml.safe_dump(
            {
                "name": "versioned-suite",
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
                "name": f"versioned-{name}",
                "suite": {"config_path": str(suite_path), "corpus_root": str(corpus)},
                "base_seed": base_seed,
                "evaluators": [{"name": "rules-baseline"}],
            }
        ),
        encoding="utf-8",
    )
    return study_path, tmp_path / f"{name}-run"


def _published_run(tmp_path: Path, name: str, base_seed: int = 21) -> Path:
    study_path, out_dir = _study_dir(tmp_path, name, base_seed)
    result = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert result.exit_code == 0, result.output
    return out_dir


def test_study_publishes_versioned_analysis_alongside(tmp_path: Path) -> None:
    """E4b: separate name/version; historical analysis.json shape untouched."""
    out_dir = _published_run(tmp_path, "v-ok")
    versioned = out_dir / analysis_filename()
    assert versioned.is_file()
    legacy = json.loads((out_dir / "analysis.json").read_text(encoding="utf-8"))
    assert "records_sha256" not in legacy
    assert "analysis_version" not in legacy
    document = read_versioned_analysis(versioned)
    assert document["analysis_version"] == ANALYSIS_DEFINITION_VERSION
    assert document["kind"] == "study"
    assert document["evaluators"] == ["rules-baseline"]
    assert document["coverage"]["rules-baseline"]["scored"] > 0
    verify_bundle(out_dir, kind="study")


def test_stale_records_rejected_even_with_fresh_marker(tmp_path: Path) -> None:
    """E4b: editing records + regenerating the marker still refuses the cache."""
    out_dir = _published_run(tmp_path, "v-stale")
    with (out_dir / "records.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"tampered": true}\n')
    write_completion(out_dir, kind="study")
    verify_bundle(out_dir, kind="study")
    with pytest.raises(AnalysisError, match="hash mismatch"):
        read_versioned_analysis(out_dir / analysis_filename())


def test_mixed_analysis_rejected(tmp_path: Path) -> None:
    """E4b: analysis bound to another run's records is refused."""
    out_a = _published_run(tmp_path, "v-mix-a", base_seed=21)
    out_b = _published_run(tmp_path, "v-mix-b", base_seed=22)
    assert (out_a / "records.jsonl").read_bytes() != (out_b / "records.jsonl").read_bytes()
    (out_a / analysis_filename()).write_bytes((out_b / analysis_filename()).read_bytes())
    write_completion(out_a, kind="study")
    with pytest.raises(AnalysisError, match="hash mismatch"):
        read_versioned_analysis(out_a / analysis_filename())


def test_coverage_mismatch_rejected(tmp_path: Path) -> None:
    """E4b: edited coverage counts do not match the bound records."""
    out_dir = _published_run(tmp_path, "v-cov")
    marker = out_dir / analysis_filename()
    document = json.loads(marker.read_text(encoding="utf-8"))
    document["coverage"]["rules-baseline"]["scored"] += 1
    marker.write_text(json.dumps(document), encoding="utf-8")
    write_completion(out_dir, kind="study")
    with pytest.raises(AnalysisError, match="coverage mismatch"):
        read_versioned_analysis(marker)


def test_unknown_version_rejected(tmp_path: Path) -> None:
    """E4b: records hash or analysis version change invalidates the cache."""
    out_dir = _published_run(tmp_path, "v-ver")
    marker = out_dir / analysis_filename()
    document = json.loads(marker.read_text(encoding="utf-8"))
    document["analysis_version"] = ANALYSIS_DEFINITION_VERSION + 1
    marker.write_text(json.dumps(document), encoding="utf-8")
    write_completion(out_dir, kind="study")
    with pytest.raises(AnalysisError, match="not current"):
        read_versioned_analysis(marker)


def test_compare_consumes_verified_analysis(tmp_path: Path) -> None:
    """E4b: CLI compare reads the same verified analysis report does."""
    out_dir = _published_run(tmp_path, "v-compare")
    result = CliRunner().invoke(cli, ["compare", str(out_dir)])
    assert result.exit_code == 0, result.output
    assert "rules-baseline" in result.output
    assert "accuracy" in result.output


def test_report_renders_from_verified_analysis(tmp_path: Path) -> None:
    """E4b: CLI report --analysis renders without recomputing."""
    out_dir = _published_run(tmp_path, "v-report")
    out = tmp_path / "report.md"
    result = CliRunner().invoke(
        cli,
        [
            "report",
            str(out_dir / "records.jsonl"),
            "--analysis",
            str(out_dir / analysis_filename()),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    text = out.read_text(encoding="utf-8")
    assert f"analysis v{ANALYSIS_DEFINITION_VERSION}" in text
    assert "rules-baseline" in text


def test_republish_retires_obsolete_analysis_versions(tmp_path: Path) -> None:
    study_path, out_dir = _study_dir(tmp_path, "v-republish")
    runner = CliRunner()
    first = runner.invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert first.exit_code == 0, first.output

    stale = out_dir / "analysis-v1.json"
    assert stale != out_dir / analysis_filename()
    stale.write_text('{"obsolete": true}\n', encoding="utf-8")

    second = runner.invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert second.exit_code == 0, second.output
    assert sorted(p.name for p in out_dir.glob("analysis-v*.json")) == [analysis_filename()]
    assert read_versioned_analysis(out_dir / analysis_filename())["analysis_version"] == (
        ANALYSIS_DEFINITION_VERSION
    )


def test_compare_refuses_ambiguous_versions(tmp_path: Path) -> None:
    """E4b: two versioned analyses in one dir is an explicit error."""
    out_dir = _published_run(tmp_path, "v-amb")
    (out_dir / f"analysis-v{ANALYSIS_DEFINITION_VERSION + 1}.json").write_bytes(
        (out_dir / analysis_filename()).read_bytes()
    )
    result = CliRunner().invoke(cli, ["compare", str(out_dir)])
    assert result.exit_code != 0
    assert "ambiguous" in result.output


def test_consumers_call_the_verified_reader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Bypass regression: compare/report fail when the verified reader refuses."""
    import sloplab.reporting.analysis as analysis_module

    def _refuse(path: Path) -> Any:
        _ = path
        raise AnalysisError("verified reader refused (spy)")

    monkeypatch.setattr(analysis_module, "read_versioned_analysis", _refuse)
    out_dir = _published_run(tmp_path, "v-spy")
    assert CliRunner().invoke(cli, ["compare", str(out_dir)]).exit_code != 0
    assert (
        CliRunner()
        .invoke(
            cli,
            [
                "report",
                str(out_dir / "records.jsonl"),
                "--analysis",
                str(out_dir / analysis_filename()),
            ],
        )
        .exit_code
        != 0
    )


def _direct_writer_inputs(records_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Minimal valid bundles/coverage for direct writer calls (no CLI run)."""
    _ = records_path
    bundles: dict[str, Any] = {"rules-baseline": {"evaluator_name": "rules-baseline"}}
    coverage: dict[str, Any] = {
        "rules-baseline": {"planned": 1, "scored": 1, "failed": 0, "not_run": 0}
    }
    return bundles, coverage


def _seeded_versioned_dir(tmp_path: Path, name: str) -> tuple[Path, Path, str, str]:
    """Out dir with a current-version file and one non-current version file."""
    out_dir = tmp_path / name
    out_dir.mkdir()
    target = out_dir / analysis_filename()
    old_target_text = '{"published": "previous"}\n'
    target.write_text(old_target_text, encoding="utf-8")
    stale = out_dir / f"analysis-v{ANALYSIS_DEFINITION_VERSION + 1}.json"
    old_stale_text = '{"published": "obsolete"}\n'
    stale.write_text(old_stale_text, encoding="utf-8")
    assert stale != target
    return out_dir, target, old_target_text, old_stale_text


def test_missing_records_keeps_existing_versioned_files(tmp_path: Path) -> None:
    """Sözleşme eki (1): missing records_path errors; existing files untouched."""
    out_dir, target, old_target_text, old_stale_text = _seeded_versioned_dir(
        tmp_path, "w-missing-records"
    )
    records_path = tmp_path / "records.jsonl"
    records_path.write_text('{"case": 1}\n', encoding="utf-8")
    bundles, coverage = _direct_writer_inputs(records_path)
    with pytest.raises(AnalysisError, match="records file missing"):
        write_versioned_analysis(
            out_dir,
            records_path=out_dir / "no-such-records.jsonl",
            bundles=bundles,
            coverage=coverage,
        )
    assert target.read_text(encoding="utf-8") == old_target_text
    stale = out_dir / f"analysis-v{ANALYSIS_DEFINITION_VERSION + 1}.json"
    assert stale.read_text(encoding="utf-8") == old_stale_text


def test_write_failure_keeps_old_file_and_leaves_no_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sözleşme eki (2): forced document-write failure; old file kept, no debris."""
    import json as json_module

    out_dir, target, old_target_text, old_stale_text = _seeded_versioned_dir(
        tmp_path, "w-write-failure"
    )
    records_path = tmp_path / "records.jsonl"
    records_path.write_text('{"case": 1}\n', encoding="utf-8")
    bundles, coverage = _direct_writer_inputs(records_path)

    def _boom(*args: Any, **kwargs: Any) -> str:
        _ = (args, kwargs)
        raise RuntimeError("forced serialization failure")

    monkeypatch.setattr(json_module, "dumps", _boom)
    with pytest.raises(RuntimeError, match="forced serialization failure"):
        write_versioned_analysis(
            out_dir, records_path=records_path, bundles=bundles, coverage=coverage
        )
    assert target.read_text(encoding="utf-8") == old_target_text
    stale = out_dir / f"analysis-v{ANALYSIS_DEFINITION_VERSION + 1}.json"
    assert stale.read_text(encoding="utf-8") == old_stale_text
    assert sorted(p.name for p in out_dir.iterdir()) == sorted([target.name, stale.name])


def test_successful_publish_leaves_only_current_version(tmp_path: Path) -> None:
    """Sözleşme eki (3): success path retires obsolete files, keeps the current one."""
    out_dir, _, _, _ = _seeded_versioned_dir(tmp_path, "w-success")
    records_path = tmp_path / "records.jsonl"
    records_path.write_text('{"case": 1}\n', encoding="utf-8")
    bundles, coverage = _direct_writer_inputs(records_path)
    published = write_versioned_analysis(
        out_dir, records_path=records_path, bundles=bundles, coverage=coverage
    )
    assert published == out_dir / analysis_filename()
    assert sorted(p.name for p in out_dir.glob("analysis-v*.json")) == [analysis_filename()]
    document = json.loads(published.read_text(encoding="utf-8"))
    assert document["analysis_version"] == ANALYSIS_DEFINITION_VERSION


def test_study_analysis_write_failure_keeps_previous_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F1: forced failure during the legacy analysis.json write keeps the previous file."""
    import sloplab.reporting.analysis as analysis_module

    study_path, out_dir = _study_dir(tmp_path, "w-study-atomic")
    first = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert first.exit_code == 0, first.output
    legacy = out_dir / "analysis.json"
    old_text = legacy.read_text(encoding="utf-8")

    def _boom(target: Path, payload: str) -> None:
        raise RuntimeError("forced study analysis write failure")

    monkeypatch.setattr(analysis_module, "write_text_atomic", _boom)
    second = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert second.exit_code != 0
    assert legacy.read_text(encoding="utf-8") == old_text
    assert list(out_dir.glob("*.tmp")) == []


def test_atomic_write_keeps_normal_permissions(tmp_path: Path) -> None:
    """F2: atomically published files honor umask (0644-style), not mkstemp 0600."""
    import os as os_module
    import stat as stat_module

    from sloplab.reporting.analysis import write_text_atomic

    target = tmp_path / "analysis.json"
    write_text_atomic(target, "{}\n")
    umask = os_module.umask(0)
    os_module.umask(umask)
    assert stat_module.S_IMODE(target.stat().st_mode) == (0o666 & ~umask)


def test_replace_failure_removes_temp_and_keeps_old_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F5: failure injected after the temp file exists removes it; the old file stays."""
    import os as os_module

    from sloplab.reporting.analysis import write_text_atomic

    target = tmp_path / "analysis.json"
    old_text = '{"published": "previous"}\n'
    target.write_text(old_text, encoding="utf-8")

    def _boom_replace(src: Any, dst: Any) -> None:
        raise OSError("forced replace failure")

    monkeypatch.setattr(os_module, "replace", _boom_replace)
    with pytest.raises(OSError, match="forced replace failure"):
        write_text_atomic(target, '{"published": "new"}\n')
    assert target.read_text(encoding="utf-8") == old_text
    assert list(tmp_path.glob("*.tmp")) == []
