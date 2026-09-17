"""E2b-r2: single execution chain and raceless dispatch accounting. No live calls."""

from __future__ import annotations

import importlib.util
import json
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

import sloplab.evaluators.llm.adapter as adapter_module
from sloplab.corpus.loader import discover_fixtures
from sloplab.evaluators.llm.adapter import (
    HttpLLMClient,
    LlmEvaluator,
    LLMResponse,
)
from sloplab.evaluators.llm.failures import DeadlineExceeded
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.pilot import (
    CountingClient,
    ThrottledClient,
    run_llm_pilot,
)
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import materialize_suite
from sloplab.scoring.harness import build_cases
from tests._helpers import write_canonical_fixture
from tests.regression.test_dispatch_accounting import (
    FakeClock,
    _FakeHttpResponse,
    _valid_payload_text,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "llm_bench_r2", REPO_ROOT / "scripts" / "llm_bench.py"
)
assert _spec is not None and _spec.loader is not None
llm_bench: ModuleType = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(llm_bench)


class _RecordingTransport:
    def __init__(self, payload_text: str) -> None:
        self.payload_text = payload_text
        self.calls = 0

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        _ = prompt
        return LLMResponse(text=self.payload_text, latency_ms=1)


def _workspace(tmp_path: Path) -> dict[str, Any]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Chain clean report",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "b-000",
        fixture_id="canonical-b-000",
        title="Chain second report",
        report_class="valid",
    )
    suite = {
        "name": "chain-suite",
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
    return {"corpus": corpus, "out": out_root, "cases": cases}


def _write_template(tmp_path: Path) -> Path:
    path = tmp_path / "triage-r2.md"
    path.write_text("Route carefully. R2-MARKER\n\n{report_text}\n", encoding="utf-8")
    return path


def _pilot_config(
    prompt_file: Path, max_requests: int = 50, min_interval_ms: int = 0
) -> LLMPilotConfig:
    return LLMPilotConfig.model_validate(
        {
            "schema_version": 2,
            "name": "chain-pilot",
            "suite": {"config_path": "benchmarks/suites/v1-core.yaml", "corpus_root": "corpus"},
            "base_seed": 21,
            "repeats": 1,
            "model_env": "R2_MODEL",
            "endpoint_env": "R2_ENDPOINT",
            "api_key_env": "R2_API_KEY",
            "prompt_file": str(prompt_file),
            "budget": {"max_requests": max_requests, "min_interval_ms": min_interval_ms},
            "case_selection": "canonical_first",
            "max_cases": None,
        }
    )


def _read_outcomes(result: Any) -> list[dict[str, Any]]:
    assert result.outcomes_path is not None
    return [
        json.loads(line)
        for line in result.outcomes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_deadline_race_returns_reservation_unconsumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R2 acceptance 1: outer check passes, HTTP check refuses; nothing counted."""
    import sloplab.experiments.pilot as pilot_module

    pilot_clock = FakeClock(now=1000.0, advance_on_sleep=False)
    http_clock = FakeClock(now=2000.0, advance_on_sleep=False)
    monkeypatch.setattr(pilot_module, "time", pilot_clock)
    monkeypatch.setattr(adapter_module, "time", http_clock)
    monkeypatch.setenv("E2B_R2_API_KEY", "test-key-never-used")
    urlopen_calls: list[Any] = []

    def _fake_urlopen(request: Any, timeout: Any = None) -> _FakeHttpResponse:
        urlopen_calls.append(timeout)
        _ = request
        return _FakeHttpResponse(_valid_payload_text())

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    http = HttpLLMClient(
        model="test-model",
        api_key_env="E2B_R2_API_KEY",
        endpoint="https://example.invalid/v1",
        timeout_s=60.0,
    )
    counting = CountingClient(http, max_requests=1)
    counting.set_deadline(1500.0)

    with pytest.raises(DeadlineExceeded):
        counting.complete("hello")
    assert urlopen_calls == []
    assert counting.physical_dispatches == 0
    assert counting.errors == 0
    assert counting.timeouts == 0

    # The returned reservation still funds a later real dispatch (cap intact).
    http_clock.now = 1000.0
    response = counting.complete("hello")
    assert json.loads(response.text)["decision"] == "accept"
    assert len(urlopen_calls) == 1
    assert counting.physical_dispatches == 1


def test_direct_pilot_applies_config_pacing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R2 acceptance 2: bare chain + config pacing paces real dispatches."""
    import sloplab.experiments.pilot as pilot_module

    fake = FakeClock(now=1000.0)
    monkeypatch.setattr(pilot_module, "time", fake)
    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:2]
    template = _write_template(tmp_path)
    transport = _RecordingTransport(_valid_payload_text())
    evaluator = LlmEvaluator(
        client=CountingClient(transport, max_requests=50), max_retries=0, enabled=True
    )
    result = run_llm_pilot(
        _pilot_config(template, min_interval_ms=500),
        evaluator,
        cases,
        tmp_path,
        tmp_path / "o-pacing",
    )
    assert transport.calls == 2
    assert fake.sleeps == [pytest.approx(0.5)]
    assert [o["status"] for o in _read_outcomes(result)] == ["success", "success"]
    assert result.evaluations_attempted == 2


def test_script_uses_shared_chain_builder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    """R2 acceptance 2 (second half): script builds via the shared constructor."""
    import sloplab.experiments.pilot as pilot_module

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
    real_builder = pilot_module.build_pilot_client_chain

    def _spy(transport: Any, *, min_interval_ms: int, max_requests: int, **kwargs: Any) -> Any:
        seen.append({"min_interval_ms": min_interval_ms, "max_requests": max_requests, **kwargs})
        return real_builder(
            transport,
            min_interval_ms=min_interval_ms,
            max_requests=max_requests,
            **kwargs,
        )

    monkeypatch.setattr(llm_bench, "build_pilot_client_chain", _spy)
    config = tmp_path / "r2-pilot.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "name": "r2-pilot",
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
                    "min_interval_ms": 250,
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
    assert len(seen) == 1
    assert seen[0]["min_interval_ms"] == 250
    assert seen[0]["max_requests"] == 180
    assert seen[0].get("sleep_cap_s", None) is None
    capsys.readouterr()


def test_miswired_chains_rejected_before_dispatch(tmp_path: Path) -> None:
    """R2 acceptance 3: misordered/double/mismatched/ownerless chains fail fast."""
    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:1]
    template = _write_template(tmp_path)

    def _run(client: Any, config: LLMPilotConfig, name: str) -> Any:
        evaluator = LlmEvaluator(client=client, max_retries=0, enabled=True)
        return run_llm_pilot(config, evaluator, cases, tmp_path, tmp_path / name)

    misordered_transport = _RecordingTransport(_valid_payload_text())
    with pytest.raises(ValueError, match="canonical"):
        _run(
            CountingClient(
                ThrottledClient(misordered_transport, min_interval_ms=0),
                max_requests=50,
            ),
            _pilot_config(template),
            "o-misordered",
        )
    assert misordered_transport.calls == 0

    double_transport = _RecordingTransport(_valid_payload_text())
    with pytest.raises(ValueError, match="more than one"):
        _run(
            ThrottledClient(
                CountingClient(
                    CountingClient(double_transport, max_requests=50),
                    max_requests=50,
                ),
                min_interval_ms=0,
            ),
            _pilot_config(template),
            "o-double",
        )
    assert double_transport.calls == 0

    mismatch_transport = _RecordingTransport(_valid_payload_text())
    with pytest.raises(ValueError, match="diverges"):
        _run(
            ThrottledClient(
                CountingClient(mismatch_transport, max_requests=50),
                min_interval_ms=100,
            ),
            _pilot_config(template, min_interval_ms=500),
            "o-mismatch",
        )
    assert mismatch_transport.calls == 0

    ownerless_transport = _RecordingTransport(_valid_payload_text())
    with pytest.raises(ValueError, match="built around CountingClient"):
        _run(ownerless_transport, _pilot_config(template), "o-ownerless")
    assert ownerless_transport.calls == 0
