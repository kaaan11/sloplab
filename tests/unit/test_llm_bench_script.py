"""Mock-based tests for scripts/llm_bench.py and the llm-benchmark workflow.

No live API calls: the HTTP client is replaced by an in-process fake, so every
budget/pacing/provenance behavior is exercised deterministically.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from sloplab.evaluators.llm.adapter import LLMResponse

REPO_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "llm_bench", REPO_ROOT / "scripts" / "llm_bench.py"
)
assert _spec is not None and _spec.loader is not None
llm_bench: ModuleType = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(llm_bench)

WORKFLOW = REPO_ROOT / ".github/workflows/llm-benchmark.yml"

VALID_PAYLOAD = json.dumps(
    {
        "decision": "accept",
        "confidence": 0.8,
        "dimensions": {
            d: 0.7
            for d in (
                "reproducibility",
                "evidence_completeness",
                "claim_evidence_consistency",
                "impact_calibration",
                "scope_consistency",
            )
        },
        "findings": [],
        "rationale": "ok",
    }
)


class FakeHttp:
    """In-process stand-in for HttpLLMClient; records every dispatch."""

    last: FakeHttp | None = None
    instances: list[FakeHttp] = []

    def __init__(self, *, model: str, api_key_env: str, endpoint: str) -> None:
        self.model = model
        self.api_key_env = api_key_env
        self.endpoint = endpoint
        self.calls = 0
        type(self).instances.append(self)
        type(self).last = self

    def complete(self, prompt: str) -> LLMResponse:
        _ = prompt
        self.calls += 1
        return LLMResponse(text=VALID_PAYLOAD, latency_ms=1)


@pytest.fixture()
def fake_http(monkeypatch: pytest.MonkeyPatch) -> type[FakeHttp]:
    monkeypatch.setenv("SLOPLAB_LLM_MODEL", "openai/gpt-oss-20b:free")
    monkeypatch.setenv("SLOPLAB_LLM_ENDPOINT", "https://example.invalid/v1")
    monkeypatch.setattr(llm_bench, "HttpLLMClient", FakeHttp)
    FakeHttp.instances = []
    FakeHttp.last = None
    return FakeHttp


class TestSmokeDefaults:
    def test_default_plan_is_three_cases_nine_requests_cap(
        self, fake_http: type[FakeHttp], tmp_path: Path, capsys: Any
    ) -> None:
        out = tmp_path / "llm-bench-results.jsonl"
        rc = llm_bench.main(["--out", str(out)])

        assert rc == 0
        printed = capsys.readouterr().out
        assert "worst-case 9 requests" in printed
        assert fake_http.last is not None and fake_http.last.calls == 3
        lines = out.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3


class TestPreflightRejection:
    def test_oversized_plan_rejected_before_any_request(
        self,
        fake_http: type[FakeHttp],
        tmp_path: Path,
        capsys: Any,
    ) -> None:
        config = tmp_path / "tiny-pilot.yaml"
        config.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 2,
                    "name": "tiny-pilot",
                    "suite": {
                        "config_path": "benchmarks/suites/v1-core.yaml",
                        "corpus_root": "corpus",
                    },
                    "base_seed": 1,
                    "repeats": 3,
                    "model_env": "SLOPLAB_LLM_MODEL",
                    "endpoint_env": "SLOPLAB_LLM_ENDPOINT",
                    "api_key_env": "SLOPLAB_LLM_API_KEY",
                    "prompt_file": "experiments/prompts/triage-v1.md",
                    "budget": {
                        "max_requests": 5,
                        "request_timeout_s": 60,
                        "max_retries_per_case": 2,
                        "min_interval_ms": 0,
                    },
                    "case_selection": "canonical_first",
                }
            ),
            encoding="utf-8",
        )
        out = tmp_path / "results.jsonl"
        rc = llm_bench.main(["--config", str(config), "--max-cases", "3", "--out", str(out)])

        assert rc == 2
        err = capsys.readouterr().err
        assert "caps at 5" in err and "--max-cases" in err
        assert fake_http.instances == []
        assert not out.exists()


class TestOutputsAndProvenance:
    def test_records_and_manifest_bundle_are_written(
        self, fake_http: type[FakeHttp], tmp_path: Path, capsys: Any
    ) -> None:
        out = tmp_path / "llm-bench-results.jsonl"
        rc = llm_bench.main(["--max-cases", "2", "--repeats", "2", "--out", str(out)])

        assert rc == 0
        bundle = tmp_path / "llm-bench-results.bundle"
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["kind"] == "llm-pilot"
        assert manifest["repeats"] == 2
        assert manifest["selected_cases"] == 2
        assert manifest["budget"]["max_requests"] == 180
        assert manifest["counters"]["requests"] == 4
        assert manifest["prompt_hash"]
        records = [json.loads(line) for line in out.read_text().splitlines()]
        assert len(records) == 4
        repeats = sorted(r["evaluation_metadata"]["repeat_index"] for r in records)
        assert repeats == [0, 0, 1, 1]
        printed = capsys.readouterr().out
        assert "requests used: 4" in printed


class TestEnvGuard:
    def test_missing_model_env_fails_fast(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Any
    ) -> None:
        monkeypatch.delenv("SLOPLAB_LLM_MODEL", raising=False)
        monkeypatch.setenv("SLOPLAB_LLM_ENDPOINT", "https://example.invalid/v1")
        rc = llm_bench.main(["--out", str(tmp_path / "x.jsonl")])

        assert rc == 2
        assert "SLOPLAB_LLM_MODEL" in capsys.readouterr().err


class TestWorkflowContract:
    def test_manual_only_and_wired_to_budget_runner(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        doc = yaml.safe_load(raw)

        triggers = doc[True] if True in doc else doc.get("on")  # yaml 1.1 "on" quirk
        assert set(triggers) == {"workflow_dispatch"}, "must stay manual-only"
        job = doc["jobs"]["run"]
        assert job["environment"] == "llm-bench"
        steps = job["steps"]
        run_commands = " ".join(s.get("run", "") for s in steps)
        assert "scripts/llm_bench.py" in run_commands
        upload = next(
            s for s in steps if str(s.get("uses", "")).startswith("actions/upload-artifact")
        )
        assert "llm-bench-results.bundle/" in upload["with"]["path"]
        assert "MANUAL-ONLY" in raw
