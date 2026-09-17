"""E3b: every reader honors the integrity boundary; no silent bypass."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

import sloplab.cli.main as cli_module
from sloplab.cli.main import cli
from sloplab.corpus.loader import discover_fixtures
from sloplab.evaluators.llm.adapter import LlmEvaluator, LLMResponse
from sloplab.experiments.bundle import BundleError, verify_bundle
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.pilot import build_pilot_client_chain, run_llm_pilot
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import materialize_suite
from sloplab.scoring.harness import build_cases
from tests._helpers import write_canonical_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "benchmarks" / "results" / "v1-core-example"


def test_compare_reads_legacy_openly() -> None:
    result = CliRunner().invoke(cli, ["compare", str(EXAMPLE)])
    assert result.exit_code == 0, result.output
    assert "legacy" in result.output
    assert "accuracy" in result.output


def test_compare_refuses_broken_marker(tmp_path: Path) -> None:
    (tmp_path / "metrics-x.json").write_text('{"evaluator_name": "x"}', encoding="utf-8")
    (tmp_path / "completion.json").write_text("not json", encoding="utf-8")
    result = CliRunner().invoke(cli, ["compare", str(tmp_path)])
    assert result.exit_code != 0
    assert "completion" in result.output


def test_compare_refuses_unrecognizable(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["compare", str(tmp_path)])
    assert result.exit_code != 0


def test_report_reads_legacy_openly(tmp_path: Path) -> None:
    # --out keeps the committed historical bundle untouched.
    out = tmp_path / "report.md"
    result = CliRunner().invoke(cli, ["report", str(EXAMPLE / "run.jsonl"), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert "legacy" in result.output
    assert out.is_file()


def test_report_refuses_broken_marker(tmp_path: Path) -> None:
    run = tmp_path / "run.jsonl"
    run.write_text("", encoding="utf-8")
    (tmp_path / "completion.json").write_text("not json", encoding="utf-8")
    result = CliRunner().invoke(cli, ["report", str(run)])
    assert result.exit_code != 0
    assert "completion" in result.output


def test_readers_call_the_boundary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Bypass regression: compare/report fail when the boundary refuses."""

    def _refuse(path: Path, *, purpose: str) -> str:
        _ = (path, purpose)
        raise BundleError("boundary refused (spy)")

    monkeypatch.setattr(cli_module, "open_result_dir", _refuse)
    assert CliRunner().invoke(cli, ["compare", str(EXAMPLE)]).exit_code != 0
    out = tmp_path / "report.md"
    assert (
        CliRunner().invoke(cli, ["report", str(EXAMPLE / "run.jsonl"), "--out", str(out)]).exit_code
        != 0
    )
    assert not out.exists()


def test_llm_bench_consumes_only_verified_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    import importlib.util

    import sloplab.experiments.bundle as bundle_module

    spec = importlib.util.spec_from_file_location(
        "llm_bench_e3b", REPO_ROOT / "scripts" / "llm_bench.py"
    )
    assert spec is not None and spec.loader is not None
    llm_bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(llm_bench)

    monkeypatch.setenv("SLOPLAB_LLM_MODEL", "openai/gpt-oss-20b:free")
    monkeypatch.setenv("SLOPLAB_LLM_ENDPOINT", "https://example.invalid/v1")
    monkeypatch.setenv("SLOPLAB_LLM_API_KEY", "test-key-never-logged")

    payload = json.dumps(
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

    class _ScriptFake:
        def __init__(self, **kwargs: Any) -> None:
            _ = kwargs

        def complete(self, prompt: str) -> LLMResponse:
            _ = prompt
            return LLMResponse(text=payload, latency_ms=1)

    monkeypatch.setattr(llm_bench, "HttpLLMClient", _ScriptFake)

    def _refuse(bundle_dir: Path, *, kind: str) -> Any:
        _ = (bundle_dir, kind)
        raise BundleError("bundle broken (spy)")

    monkeypatch.setattr(bundle_module, "verify_bundle", _refuse)
    config = tmp_path / "e3b-pilot.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "name": "e3b-pilot",
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
    assert rc == 1
    assert "bundle error" in capsys.readouterr().err


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


class _FailSecondTransport:
    def __init__(self, payload_text: str) -> None:
        self.payload_text = payload_text
        self.calls = 0

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        _ = prompt
        if self.calls == 2:
            raise TimeoutError("simulated outage")
        return LLMResponse(text=self.payload_text, latency_ms=1)


def _pilot_workspace(tmp_path: Path) -> dict[str, Any]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Coverage clean report",
        report_class="valid",
    )
    suite = {
        "name": "coverage-suite",
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
    template = tmp_path / "triage-e3b.md"
    template.write_text("Route carefully. E3B-MARKER\n\n{report_text}\n", encoding="utf-8")
    return {"cases": cases, "template": template}


def _pilot_config(prompt_file: Path) -> LLMPilotConfig:
    return LLMPilotConfig.model_validate(
        {
            "schema_version": 2,
            "name": "coverage-pilot",
            "suite": {"config_path": "benchmarks/suites/v1-core.yaml", "corpus_root": "corpus"},
            "base_seed": 21,
            "repeats": 1,
            "model_env": "E3B_MODEL",
            "endpoint_env": "E3B_ENDPOINT",
            "api_key_env": "E3B_API_KEY",
            "prompt_file": str(prompt_file),
            "budget": {"max_requests": 50, "min_interval_ms": 0},
            "case_selection": "canonical_first",
            "max_cases": None,
        }
    )


def test_bundle_complete_and_coverage_sufficient_are_separate(tmp_path: Path) -> None:
    """Technical publication and scientific sufficiency are never equated."""
    paths = _pilot_workspace(tmp_path)
    assert len(paths["cases"]) == 2
    transport = _FailSecondTransport(_valid_payload_text())
    client = build_pilot_client_chain(transport, min_interval_ms=0, max_requests=50)
    evaluator = LlmEvaluator(client=client, max_retries=0, enabled=True)
    result = run_llm_pilot(
        _pilot_config(paths["template"]), evaluator, paths["cases"], tmp_path, tmp_path / "out"
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["bundle_complete"] is True
    assert manifest["coverage_sufficient"] is False
    assert manifest["bundle_complete"] != manifest["coverage_sufficient"]
    # Technically complete: the strict reader still verifies the bundle.
    verify_bundle(tmp_path / "out", kind="llm-pilot")

    full = run_llm_pilot(
        _pilot_config(paths["template"]),
        LlmEvaluator(
            client=build_pilot_client_chain(
                _FailSecondTransport(_valid_payload_text()), min_interval_ms=0, max_requests=50
            ),
            max_retries=1,
            enabled=True,
        ),
        paths["cases"],
        tmp_path,
        tmp_path / "out-full",
    )
    full_manifest = json.loads(full.manifest_path.read_text(encoding="utf-8"))
    assert full_manifest["bundle_complete"] is True
    assert full_manifest["coverage_sufficient"] is True
