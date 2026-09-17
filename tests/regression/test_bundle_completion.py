"""E3a: bundle completion markers, strict reader, legacy recognition.

Fault injection at every write boundary: missing, corrupt, swapped, mixed,
and marker-less bundles are rejected by the strict reader; only fully
published bundles verify. No live calls.
"""

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
    classify_bundle,
    verify_bundle,
    write_completion,
)
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.pilot import build_pilot_client_chain, run_llm_pilot
from sloplab.experiments.study import run_deterministic_study
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import materialize_suite
from sloplab.scoring.harness import build_cases
from tests._helpers import write_canonical_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _workspace(tmp_path: Path, marker: str = "E3A") -> dict[str, Any]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Bundle clean report",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "b-000",
        fixture_id="canonical-b-000",
        title="Bundle second report",
        report_class="valid",
    )
    suite = {
        "name": "bundle-suite",
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
    template = tmp_path / "triage-e3a.md"
    template.write_text(f"Route carefully. {marker}-MARKER\n\n{{report_text}}\n", encoding="utf-8")
    return {"corpus": corpus, "out": out_root, "cases": cases, "template": template}


def _pilot_config(prompt_file: Path, max_requests: int = 50) -> LLMPilotConfig:
    return LLMPilotConfig.model_validate(
        {
            "schema_version": 2,
            "name": "bundle-pilot",
            "suite": {"config_path": "benchmarks/suites/v1-core.yaml", "corpus_root": "corpus"},
            "base_seed": 21,
            "repeats": 1,
            "model_env": "E3A_MODEL",
            "endpoint_env": "E3A_ENDPOINT",
            "api_key_env": "E3A_API_KEY",
            "prompt_file": str(prompt_file),
            "budget": {"max_requests": max_requests, "min_interval_ms": 0},
            "case_selection": "canonical_first",
            "max_cases": None,
        }
    )


def _pilot_bundle(tmp_path: Path, name: str, case_count: int = 1) -> Any:
    paths = _workspace(tmp_path / name, marker=name.upper())
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:case_count]
    transport = _RecordingTransport(_valid_payload_text())
    client = build_pilot_client_chain(transport, min_interval_ms=0, max_requests=50)
    evaluator = LlmEvaluator(client=client, max_retries=0, enabled=True)
    return run_llm_pilot(
        _pilot_config(paths["template"]), evaluator, cases, tmp_path, tmp_path / f"{name}-out"
    )


def _study_bundle(tmp_path: Path, name: str, base_seed: int = 21) -> Path:
    corpus = tmp_path / name / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Study bundle report",
        report_class="valid",
    )
    suite_path = tmp_path / name / "suite.yaml"
    suite_path.write_text(
        yaml.safe_dump(
            {
                "name": "study-bundle-suite",
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
                "name": f"study-bundle-{name}",
                "suite": {"config_path": str(suite_path), "corpus_root": str(corpus)},
                "base_seed": base_seed,
                "evaluators": [{"name": "rules-baseline"}],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / f"{name}-run"
    result = CliRunner().invoke(cli, ["study", str(study_path), "--out", str(out)])
    assert result.exit_code == 0, result.output
    return out


# --- pilot boundary --------------------------------------------------------


def test_pilot_complete_bundle_verifies(tmp_path: Path) -> None:
    result = _pilot_bundle(tmp_path, "ok")
    assert result.completion_path is not None and result.completion_path.is_file()
    document = verify_bundle(tmp_path / "ok-out", kind="llm-pilot")
    assert set(document["files"]) == {"manifest.json", "records.jsonl", "outcomes.jsonl"}
    assert classify_bundle(tmp_path / "ok-out") == "complete"


def test_pilot_marker_published_after_required_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The marker call observes all required files already written."""
    import sloplab.experiments.bundle as bundle_module

    seen: dict[str, bool] = {}
    real_write = bundle_module.write_completion

    def _spy(out_dir: Path, *, kind: str) -> Path:
        seen["records"] = (out_dir / "records.jsonl").is_file()
        seen["outcomes"] = (out_dir / "outcomes.jsonl").is_file()
        seen["manifest"] = (out_dir / "manifest.json").is_file()
        return real_write(out_dir, kind=kind)

    monkeypatch.setattr(bundle_module, "write_completion", _spy)
    _pilot_bundle(tmp_path, "order")
    assert seen == {"records": True, "outcomes": True, "manifest": True}


def test_pilot_rewrite_invalidates_old_marker_before_dispatch(tmp_path: Path) -> None:
    out = tmp_path / "rewrite-out"
    first = _pilot_bundle(tmp_path, "rewrite")
    assert first.out_dir == out and classify_bundle(out) == "complete"

    paths = _workspace(tmp_path / "rewrite-next", marker="REWRITE-NEXT")
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:1]

    class _CheckingTransport(_RecordingTransport):
        def complete(self, prompt: str) -> LLMResponse:
            assert classify_bundle(out) != "complete"
            return super().complete(prompt)

    client = build_pilot_client_chain(
        _CheckingTransport(_valid_payload_text()), min_interval_ms=0, max_requests=50
    )
    evaluator = LlmEvaluator(client=client, max_retries=0, enabled=True)
    run_llm_pilot(_pilot_config(paths["template"]), evaluator, cases, tmp_path, out)
    assert classify_bundle(out) == "complete"


def test_pilot_missing_file_rejected(tmp_path: Path) -> None:
    _pilot_bundle(tmp_path, "miss")
    (tmp_path / "miss-out" / "outcomes.jsonl").unlink()
    with pytest.raises(BundleError, match="missing"):
        verify_bundle(tmp_path / "miss-out", kind="llm-pilot")
    assert classify_bundle(tmp_path / "miss-out") == "incomplete"


def test_pilot_corrupt_file_rejected(tmp_path: Path) -> None:
    result = _pilot_bundle(tmp_path, "corrupt")
    with result.records_path.open("a", encoding="utf-8") as handle:
        handle.write('{"tampered": true}\n')
    with pytest.raises(BundleError, match="hash mismatch"):
        verify_bundle(tmp_path / "corrupt-out", kind="llm-pilot")


def test_pilot_swapped_manifest_rejected(tmp_path: Path) -> None:
    _pilot_bundle(tmp_path, "swap-a", case_count=1)
    other = _pilot_bundle(tmp_path, "swap-b", case_count=2)
    assert other.out_dir is not None
    (tmp_path / "swap-a-out" / "manifest.json").write_bytes(
        (tmp_path / "swap-b-out" / "manifest.json").read_bytes()
    )
    with pytest.raises(BundleError, match="hash mismatch"):
        verify_bundle(tmp_path / "swap-a-out", kind="llm-pilot")


def test_pilot_extra_file_rejected(tmp_path: Path) -> None:
    _pilot_bundle(tmp_path, "extra")
    (tmp_path / "extra-out" / "stray.txt").write_text("not part of the run\n", encoding="utf-8")
    with pytest.raises(BundleError, match="unlisted extra"):
        verify_bundle(tmp_path / "extra-out", kind="llm-pilot")


def test_pilot_missing_marker_is_legacy_shaped(tmp_path: Path) -> None:
    _pilot_bundle(tmp_path, "nomark")
    (tmp_path / "nomark-out" / "completion.json").unlink()
    with pytest.raises(BundleError, match="no completion"):
        verify_bundle(tmp_path / "nomark-out", kind="llm-pilot")
    assert classify_bundle(tmp_path / "nomark-out") == "legacy"


def test_pilot_tampered_marker_rejected(tmp_path: Path) -> None:
    _pilot_bundle(tmp_path, "tamper")
    marker = tmp_path / "tamper-out" / "completion.json"
    document = json.loads(marker.read_text(encoding="utf-8"))
    first = next(iter(document["files"]))
    document["files"][first] = "0" * 64
    marker.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(BundleError, match="hash mismatch"):
        verify_bundle(tmp_path / "tamper-out", kind="llm-pilot")
    assert classify_bundle(tmp_path / "tamper-out") == "incomplete"


def test_pilot_kind_mismatch_rejected(tmp_path: Path) -> None:
    _pilot_bundle(tmp_path, "kind")
    with pytest.raises(BundleError, match="expected 'study'"):
        verify_bundle(tmp_path / "kind-out", kind="study")


def test_write_completion_refuses_short_set(tmp_path: Path) -> None:
    lonely = tmp_path / "lonely"
    lonely.mkdir()
    (lonely / "records.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(BundleError, match="missing"):
        write_completion(lonely, kind="llm-pilot")


# --- study boundary --------------------------------------------------------


def test_study_complete_bundle_verifies(tmp_path: Path) -> None:
    out = _study_bundle(tmp_path, "s-ok")
    document = verify_bundle(out, kind="study")
    for required in (
        "manifest.json",
        "records.jsonl",
        "suite-index.jsonl",
        "input-identity.json",
        "execution-recipe.json",
        "analysis.json",
        "results.csv",
        "report.md",
    ):
        assert required in document["files"], required
    assert any(name.startswith("adversarial/") for name in document["files"])
    assert classify_bundle(out) == "complete"


def test_study_rewrite_invalidates_old_marker_before_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _study_bundle(tmp_path, "s-rewrite")
    assert classify_bundle(out) == "complete"

    import sloplab.experiments.study as study_module

    real_materialize = study_module.materialize_suite

    def _spy(*args: Any, **kwargs: Any) -> Any:
        # E3b-r1 protocol: the runner opens the publish cycle (in-progress
        # marker, older completion retired) before its first output mutation.
        assert classify_bundle(out) != "complete"
        assert (out / "publish-in-progress.json").is_file()
        assert not (out / "completion.json").exists()
        return real_materialize(*args, **kwargs)

    monkeypatch.setattr(study_module, "materialize_suite", _spy)
    config_path = tmp_path / "s-rewrite" / "study.yaml"
    result = CliRunner().invoke(cli, ["study", str(config_path), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert classify_bundle(out) == "complete"


def test_study_missing_analysis_rejected(tmp_path: Path) -> None:
    out = _study_bundle(tmp_path, "s-miss")
    (out / "analysis.json").unlink()
    with pytest.raises(BundleError, match="missing"):
        verify_bundle(out, kind="study")
    assert classify_bundle(out) == "incomplete"


def test_study_corrupt_identity_rejected(tmp_path: Path) -> None:
    out = _study_bundle(tmp_path, "s-corrupt")
    with (out / "input-identity.json").open("a", encoding="utf-8") as handle:
        handle.write(" ")
    with pytest.raises(BundleError, match="hash mismatch"):
        verify_bundle(out, kind="study")


def test_study_mixed_runs_rejected(tmp_path: Path) -> None:
    out_a = _study_bundle(tmp_path, "s-mix-a", base_seed=21)
    out_b = _study_bundle(tmp_path, "s-mix-b", base_seed=22)
    assert (out_a / "records.jsonl").read_bytes() != (out_b / "records.jsonl").read_bytes()
    (out_a / "records.jsonl").write_bytes((out_b / "records.jsonl").read_bytes())
    with pytest.raises(BundleError, match="hash mismatch"):
        verify_bundle(out_a, kind="study")


def test_study_runner_output_without_publish_is_incomplete(tmp_path: Path) -> None:
    """E3b-r1: the library step marks in-progress, so no legacy ambiguity."""
    from sloplab.experiments.runner import load_study_config

    study_path = tmp_path / "direct" / "study.yaml"
    corpus = tmp_path / "direct" / "corpus"
    write_canonical_fixture(
        corpus, "a-000", fixture_id="canonical-a-000", title="Direct", report_class="valid"
    )
    suite_path = tmp_path / "direct" / "suite.yaml"
    suite_path.write_text(
        yaml.safe_dump(
            {
                "name": "direct-suite",
                "base_seed": 21,
                "corpus_root": str(corpus),
                "include_canonical_cases": True,
                "policies": {
                    "valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]},
                },
            }
        ),
        encoding="utf-8",
    )
    study_path.parent.mkdir(parents=True, exist_ok=True)
    study_path.write_text(
        yaml.safe_dump(
            {
                "name": "direct-study",
                "suite": {"config_path": str(suite_path), "corpus_root": str(corpus)},
                "base_seed": 21,
                "evaluators": [{"name": "rules-baseline"}],
            }
        ),
        encoding="utf-8",
    )
    result = run_deterministic_study(
        load_study_config(study_path), study_path, tmp_path / "direct-run"
    )
    assert result.manifest_path.is_file()
    assert (tmp_path / "direct-run" / "publish-in-progress.json").is_file()
    assert classify_bundle(tmp_path / "direct-run") == "incomplete"
    with pytest.raises(BundleError, match="in progress"):
        verify_bundle(tmp_path / "direct-run", kind="study")


# --- legacy recognition ----------------------------------------------------


def test_committed_example_bundle_is_legacy() -> None:
    example = REPO_ROOT / "benchmarks" / "results" / "v1-core-example"
    assert classify_bundle(example) == "legacy"
    with pytest.raises(BundleError):
        verify_bundle(example, kind="study")
    with pytest.raises(BundleError):
        verify_bundle(example, kind="llm-pilot")


def test_empty_directory_is_incomplete(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert classify_bundle(empty) == "incomplete"
    with pytest.raises(BundleError):
        verify_bundle(empty, kind="study")
