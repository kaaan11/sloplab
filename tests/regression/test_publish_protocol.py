"""E3b-r1: in-progress publish protocol separating cut runs from legacy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.corpus.loader import discover_fixtures
from sloplab.evaluators.llm.adapter import LlmEvaluator, LLMResponse
from sloplab.experiments.bundle import (
    BundleError,
    begin_publish,
    classify_bundle,
    open_result_dir,
    verify_bundle,
)
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.pilot import build_pilot_client_chain, run_llm_pilot
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import materialize_suite
from sloplab.scoring.harness import build_cases
from tests._helpers import write_canonical_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "benchmarks" / "results" / "v1-core-example"
IN_PROGRESS = "publish-in-progress.json"


def _valid_payload_text() -> str:
    return json.dumps(
        {
            "decision": "accept",
            "confidence": 0.8,
            "dimensions": {
                "reproducibility": 0.7,
                "evidence_completeness": 0.7,
                "claim_evidence_consistency": 0.7,
                "impact_calibration": 0.7,
                "scope_consistency": 0.7,
            },
            "findings": [],
            "rationale": "ok",
        }
    )


class _RecordingTransport:
    def __init__(self, payload_text: str) -> None:
        self.payload_text = payload_text
        self.calls = 0

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        _ = prompt
        return LLMResponse(text=self.payload_text, latency_ms=1)


def _workspace(tmp_path: Path, marker: str = "R1") -> dict[str, Any]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Publish clean report",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "b-000",
        fixture_id="canonical-b-000",
        title="Publish second report",
        report_class="valid",
    )
    suite = {
        "name": "publish-suite",
        "base_seed": 21,
        "corpus_root": str(corpus),
        "include_canonical_cases": True,
        "policies": {
            "valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]},
        },
    }
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(yaml.safe_dump(suite), encoding="utf-8")
    suite_config = SuiteConfig.model_validate(
        yaml.safe_load(suite_path.read_text(encoding="utf-8"))
    )
    canonical, _ = discover_fixtures(corpus)
    out_root = tmp_path / "out"
    materialize_suite(suite_config, canonical, out_root)
    cases = build_cases(out_root / "suite-index.jsonl", corpus, out_root)
    template = tmp_path / "triage-r1.md"
    template.write_text(f"Route carefully. {marker}-MARKER\n\n{{report_text}}\n", encoding="utf-8")
    return {"corpus": corpus, "out": out_root, "cases": cases, "template": template}


def _pilot_config(prompt_file: Path, max_requests: int = 50) -> LLMPilotConfig:
    return LLMPilotConfig.model_validate(
        {
            "schema_version": 2,
            "name": "publish-pilot",
            "suite": {"config_path": "benchmarks/suites/v1-core.yaml", "corpus_root": "corpus"},
            "base_seed": 21,
            "repeats": 1,
            "model_env": "R1_MODEL",
            "endpoint_env": "R1_ENDPOINT",
            "api_key_env": "R1_API_KEY",
            "prompt_file": str(prompt_file),
            "budget": {"max_requests": max_requests, "min_interval_ms": 0},
            "case_selection": "canonical_first",
            "max_cases": None,
        }
    )


def _study_dir(tmp_path: Path, name: str, base_seed: int = 21) -> tuple[Path, Path]:
    corpus = tmp_path / name / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Publish study report",
        report_class="valid",
    )
    suite_path = tmp_path / name / "suite.yaml"
    suite_path.write_text(
        yaml.safe_dump(
            {
                "name": "publish-study-suite",
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
                "name": f"publish-study-{name}",
                "suite": {"config_path": str(suite_path), "corpus_root": str(corpus)},
                "base_seed": base_seed,
                "evaluators": [{"name": "rules-baseline"}],
            }
        ),
        encoding="utf-8",
    )
    return study_path, tmp_path / f"{name}-run"


def test_pilot_marks_before_first_dispatch(tmp_path: Path) -> None:
    """R1: in-progress is visible before any output mutation or dispatch."""
    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:1]
    out_dir = tmp_path / "mark-out"
    seen: dict[str, bool] = {}

    class _ObservingTransport(_RecordingTransport):
        def complete(self, prompt: str) -> LLMResponse:
            seen["in_progress"] = (out_dir / IN_PROGRESS).is_file()
            seen["completion"] = (out_dir / "completion.json").is_file()
            return super().complete(prompt)

    transport = _ObservingTransport(_valid_payload_text())
    client = build_pilot_client_chain(transport, min_interval_ms=0, max_requests=50)
    evaluator = LlmEvaluator(client=client, max_retries=0, enabled=True)
    result = run_llm_pilot(_pilot_config(paths["template"]), evaluator, cases, tmp_path, out_dir)
    assert seen == {"in_progress": True, "completion": False}
    assert not (out_dir / IN_PROGRESS).is_file()
    assert result.completion_path is not None and result.completion_path.is_file()
    assert classify_bundle(out_dir) == "complete"


def test_study_marks_before_first_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1: the runner marks before materialization writes anything."""
    import sloplab.experiments.study as study_module

    study_path, out_dir = _study_dir(tmp_path, "s-mark")
    seen: dict[str, bool] = {}
    real_materialize = study_module.materialize_suite

    def _spy(*args: Any, **kwargs: Any) -> Any:
        seen["in_progress"] = (out_dir / IN_PROGRESS).is_file()
        seen["completion"] = (out_dir / "completion.json").is_file()
        return real_materialize(*args, **kwargs)

    monkeypatch.setattr(study_module, "materialize_suite", _spy)
    result = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert result.exit_code == 0, result.output
    assert seen == {"in_progress": True, "completion": False}
    assert not (out_dir / IN_PROGRESS).is_file()
    assert classify_bundle(out_dir) == "complete"


def _complete_pilot(tmp_path: Path, name: str) -> Path:
    paths = _workspace(tmp_path / name, marker=name.upper())
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:1]
    transport = _RecordingTransport(_valid_payload_text())
    client = build_pilot_client_chain(transport, min_interval_ms=0, max_requests=50)
    evaluator = LlmEvaluator(client=client, max_retries=0, enabled=True)
    out_dir = tmp_path / f"{name}-out"
    run_llm_pilot(_pilot_config(paths["template"]), evaluator, cases, tmp_path, out_dir)
    assert classify_bundle(out_dir) == "complete"
    return out_dir


def test_republish_marks_in_progress_before_retiring_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R1 review: no marker-less legacy window exists at publish start."""
    out_dir = _complete_pilot(tmp_path, "transition-order")
    completion = out_dir / "completion.json"
    real_unlink = Path.unlink
    observed: dict[str, str] = {}

    def _spy_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path == completion:
            observed["classify"] = classify_bundle(out_dir)
            try:
                open_result_dir(out_dir, purpose="transition-order")
                observed["open"] = "accepted"
            except BundleError:
                observed["open"] = "rejected"
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _spy_unlink)
    begin_publish(out_dir, kind="llm-pilot")
    assert observed == {"classify": "incomplete", "open": "rejected"}
    assert (out_dir / IN_PROGRESS).is_file()
    assert not completion.exists()


def test_in_progress_rejects_every_reader(tmp_path: Path) -> None:
    """R1: cut-new (in-progress residue) is incomplete for all readers."""
    out_dir = _complete_pilot(tmp_path, "cut")
    (out_dir / IN_PROGRESS).write_text('{"state": "in-progress"}\n', encoding="utf-8")
    assert classify_bundle(out_dir) == "incomplete"
    with pytest.raises(BundleError, match="in progress"):
        verify_bundle(out_dir, kind="llm-pilot")
    with pytest.raises(BundleError, match="in progress"):
        open_result_dir(out_dir, purpose="test")


def test_completion_without_final_step_still_rejected(tmp_path: Path) -> None:
    """R1: a verifiable completion plus leftover in-progress is not consumable."""
    out_dir = _complete_pilot(tmp_path, "crash")
    (out_dir / IN_PROGRESS).write_text('{"state": "in-progress"}\n', encoding="utf-8")
    # The completion file itself still verifies against the data files...
    from sloplab.experiments.bundle import read_completion

    assert read_completion(out_dir)["kind"] == "llm-pilot"
    # ...but no consumer may use the bundle until the final step completes.
    assert classify_bundle(out_dir) == "incomplete"
    with pytest.raises(BundleError, match="in progress"):
        verify_bundle(out_dir, kind="llm-pilot")
    (out_dir / IN_PROGRESS).unlink()
    assert classify_bundle(out_dir) == "complete"
    verify_bundle(out_dir, kind="llm-pilot")


def test_completion_map_ignores_protocol_files(tmp_path: Path) -> None:
    """R1: the file map covers data files only."""
    out_dir = _complete_pilot(tmp_path, "map")
    document = verify_bundle(out_dir, kind="llm-pilot")
    assert IN_PROGRESS not in document["files"]
    assert "completion.json" not in document["files"]


def test_pilot_republish_race(tmp_path: Path) -> None:
    """R1: old completion unconsumable during rewrite; strict again after."""
    out_dir = _complete_pilot(tmp_path, "race")
    paths = _workspace(tmp_path / "race-next", marker="RACE-NEXT")
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:1]
    observed: dict[str, str] = {}

    class _RaceTransport(_RecordingTransport):
        def complete(self, prompt: str) -> LLMResponse:
            observed["classify"] = classify_bundle(out_dir)
            try:
                open_result_dir(out_dir, purpose="test")
                observed["open"] = "accepted"
            except BundleError:
                observed["open"] = "rejected"
            return super().complete(prompt)

    transport = _RaceTransport(_valid_payload_text())
    client = build_pilot_client_chain(transport, min_interval_ms=0, max_requests=50)
    evaluator = LlmEvaluator(client=client, max_retries=0, enabled=True)
    run_llm_pilot(_pilot_config(paths["template"]), evaluator, cases, tmp_path, out_dir)
    assert observed == {"classify": "incomplete", "open": "rejected"}
    assert classify_bundle(out_dir) == "complete"
    assert not (out_dir / IN_PROGRESS).is_file()
    verify_bundle(out_dir, kind="llm-pilot")


def test_study_republish_race(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1: study rewrite is unconsumable mid-run, strict after finish."""
    import sloplab.experiments.study as study_module

    study_path, out_dir = _study_dir(tmp_path, "s-race")
    assert CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)]).exit_code == 0
    assert classify_bundle(out_dir) == "complete"
    observed: dict[str, str] = {}
    real_materialize = study_module.materialize_suite

    def _spy(*args: Any, **kwargs: Any) -> Any:
        observed["classify"] = classify_bundle(out_dir)
        observed["in_progress"] = str((out_dir / IN_PROGRESS).is_file())
        observed["completion"] = str((out_dir / "completion.json").is_file())
        return real_materialize(*args, **kwargs)

    monkeypatch.setattr(study_module, "materialize_suite", _spy)
    result = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert result.exit_code == 0, result.output
    assert observed == {"classify": "incomplete", "in_progress": "True", "completion": "False"}
    assert classify_bundle(out_dir) == "complete"
    assert not (out_dir / IN_PROGRESS).is_file()


def test_completion_write_interruption(tmp_path: Path) -> None:
    """R1: corrupt completion + in-progress residue stays incomplete."""
    out_dir = _complete_pilot(tmp_path, "cutwrite")
    (out_dir / "completion.json").write_text("truncated {", encoding="utf-8")
    (out_dir / IN_PROGRESS).write_text('{"state": "in-progress"}\n', encoding="utf-8")
    assert classify_bundle(out_dir) == "incomplete"
    with pytest.raises(BundleError, match="in progress"):
        verify_bundle(out_dir, kind="llm-pilot")
    with pytest.raises(BundleError, match="in progress"):
        open_result_dir(out_dir, purpose="test")


def test_readers_refuse_in_progress_dirs(tmp_path: Path) -> None:
    """R1: compare/report close the bypass on in-progress bundles."""
    out_dir = _complete_pilot(tmp_path, "gate")
    (out_dir / IN_PROGRESS).write_text('{"state": "in-progress"}\n', encoding="utf-8")
    assert CliRunner().invoke(cli, ["compare", str(out_dir)]).exit_code != 0
    run = tmp_path / "gate-run.jsonl"
    run.write_text("", encoding="utf-8")
    gated = tmp_path / "gated"
    gated.mkdir()
    (gated / "run.jsonl").write_bytes(run.read_bytes())
    (gated / "manifest.json").write_text("{}", encoding="utf-8")
    (gated / IN_PROGRESS).write_text('{"state": "in-progress"}\n', encoding="utf-8")
    out = tmp_path / "report.md"
    assert (
        CliRunner().invoke(cli, ["report", str(gated / "run.jsonl"), "--out", str(out)]).exit_code
        != 0
    )
    assert not out.exists()


def test_historical_tree_untouched_by_readers(tmp_path: Path) -> None:
    """R1: legacy reads never rewrite historical files (regression guard)."""
    import hashlib

    def _snapshot() -> dict[str, str]:
        return {
            p.relative_to(EXAMPLE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(EXAMPLE.rglob("*"))
            if p.is_file()
        }

    before = _snapshot()
    assert CliRunner().invoke(cli, ["compare", str(EXAMPLE)]).exit_code == 0
    out = tmp_path / "report.md"
    assert (
        CliRunner().invoke(cli, ["report", str(EXAMPLE / "run.jsonl"), "--out", str(out)]).exit_code
        == 0
    )
    assert _snapshot() == before


def test_mid_publish_external_reads_refuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1: while the publisher reads its own output, the boundary refuses."""
    import sloplab.reporting.writers as writers_module

    study_path, out_dir = _study_dir(tmp_path, "s-mid")
    observed: dict[str, str] = {}
    real_read = writers_module.read_run_jsonl

    def _spy(path: Path) -> Any:
        try:
            open_result_dir(path, purpose="test")
            observed["open"] = "accepted"
        except BundleError:
            observed["open"] = "rejected"
        observed["classify"] = classify_bundle(path.parent)
        return real_read(path)

    monkeypatch.setattr(writers_module, "read_run_jsonl", _spy)
    result = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out_dir)])
    assert result.exit_code == 0, result.output
    # The publisher's own internal read proceeded while every boundary read
    # of the same bytes refused: no deadlock, no silent consumption.
    assert observed == {"open": "rejected", "classify": "incomplete"}
    assert classify_bundle(out_dir) == "complete"


def test_llm_bench_gates_on_verified_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    """R1: llm_bench consumes its pilot bundle through verify_bundle."""
    import importlib.util

    import sloplab.experiments.bundle as bundle_module

    spec = importlib.util.spec_from_file_location(
        "llm_bench_r1", REPO_ROOT / "scripts" / "llm_bench.py"
    )
    assert spec is not None and spec.loader is not None
    llm_bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(llm_bench)

    monkeypatch.setenv("SLOPLAB_LLM_MODEL", "openai/gpt-oss-20b:free")
    monkeypatch.setenv("SLOPLAB_LLM_ENDPOINT", "https://example.invalid/v1")
    monkeypatch.setenv("SLOPLAB_LLM_API_KEY", "test-key-never-logged")

    class _ScriptFake:
        def __init__(self, **kwargs: Any) -> None:
            _ = kwargs

        def complete(self, prompt: str) -> LLMResponse:
            _ = prompt
            return LLMResponse(text=_valid_payload_text(), latency_ms=1)

    monkeypatch.setattr(llm_bench, "HttpLLMClient", _ScriptFake)
    seen: list[dict[str, Any]] = []
    real_verify = bundle_module.verify_bundle

    def _spy(bundle_dir: Path, *, kind: str) -> Any:
        seen.append({"dir": str(bundle_dir), "kind": kind})
        return real_verify(bundle_dir, kind=kind)

    monkeypatch.setattr(bundle_module, "verify_bundle", _spy)
    config = tmp_path / "r1-pilot.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "name": "r1-pilot",
                "suite": {
                    "config_path": "benchmarks/suites/v1-core.yaml",
                    "corpus_root": "corpus",
                },
                "base_seed": 1,
                "repeats": 1,
                "model_env": "SLOPLAB_LLM_MODEL",
                "endpoint_env": "SLOPLAB_LLM_ENDPOINT",
                "api_key_env": "SLOPLAB_LLM_API_KEY",
                "prompt_file": "experiments/prompts/triage-v1.md",
                "budget": {
                    "max_requests": 180,
                    "request_timeout_s": 60,
                    "max_retries_per_case": 2,
                    "min_interval_ms": 0,
                },
                "case_selection": "canonical_first",
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "llm-bench-results.jsonl"
    rc = llm_bench.main(
        ["--config", str(config), "--max-cases", "1", "--repeats", "1", "--out", str(out)]
    )
    assert rc == 0
    assert len(seen) == 1 and seen[0]["kind"] == "llm-pilot"
    assert seen[0]["dir"].endswith(".bundle")
    capsys.readouterr()
