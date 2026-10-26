"""E2b-r1: dispatch accounting (reservation == physical) and true run deadline.

No live calls: fake transports, a fake clock, and a monkeypatched ``urlopen``.
Chain order under test is the production order
``ThrottledClient(CountingClient(transport))``.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
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
from sloplab.evaluators.llm.failures import DeadlineExceeded, EvaluationFailure
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.pilot import (
    CountingClient,
    ThrottledClient,
    build_pilot_client_chain,
    run_llm_pilot,
)
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import materialize_suite
from sloplab.scoring.harness import build_cases
from tests._helpers import write_canonical_fixture


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


class _FailCallsTransport(_RecordingTransport):
    """Fails exactly the given 1-indexed dispatch numbers with a timeout."""

    def __init__(self, fail_calls: set[int]) -> None:
        super().__init__(_valid_payload_text())
        self.fail_calls = fail_calls

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        _ = prompt
        if self.calls in self.fail_calls:
            raise TimeoutError("simulated timeout")
        return LLMResponse(text=self.payload_text, latency_ms=1)


class _FailingTransport(_RecordingTransport):
    def __init__(self) -> None:
        super().__init__(_valid_payload_text())

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        _ = prompt
        raise TimeoutError("simulated outage")


class _Http429(Exception):
    def __init__(self, retry_after: str) -> None:
        super().__init__("too many requests")
        self.code = 429
        self.headers = {"Retry-After": retry_after}


class _Once429ThenOk:
    def __init__(self, retry_after: str) -> None:
        self.retry_after = retry_after
        self.calls = 0

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        _ = prompt
        if self.calls == 1:
            raise _Http429(self.retry_after)
        return LLMResponse(text=_valid_payload_text(), latency_ms=1)


class FakeClock:
    """Deterministic clock; sleeps only record unless told to advance."""

    def __init__(self, now: float = 1000.0, advance_on_sleep: bool = True) -> None:
        self.now = now
        self.sleeps: list[float] = []
        self.advance_on_sleep = advance_on_sleep

    def monotonic(self) -> float:
        return self.now

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        if self.advance_on_sleep:
            self.now += seconds

    def gmtime(self) -> Any:
        import time as _time

        return _time.gmtime()

    def strftime(self, fmt: str, args: Any = None) -> str:
        import time as _time

        return _time.strftime(fmt, args) if args is not None else _time.strftime(fmt)


def _workspace(tmp_path: Path) -> dict[str, Any]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Dispatch clean report",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "b-000",
        fixture_id="canonical-b-000",
        title="Dispatch second report",
        report_class="valid",
    )
    suite = {
        "name": "dispatch-suite",
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
    path = tmp_path / "triage-r1.md"
    path.write_text("Route carefully. R1-MARKER\n\n{report_text}\n", encoding="utf-8")
    return path


def _pilot_config(prompt_file: Path, max_requests: int = 50) -> LLMPilotConfig:
    return LLMPilotConfig.model_validate(
        {
            "schema_version": 2,
            "name": "dispatch-pilot",
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


def _read_outcomes(result: Any) -> list[dict[str, Any]]:
    assert result.outcomes_path is not None
    return [
        json.loads(line)
        for line in result.outcomes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_refused_pacing_wait_consumes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """R1 acceptance 1: reviewer counterexample at client level (fake clock)."""
    import sloplab.experiments.pilot as pilot_module

    fake = FakeClock(now=1000.0)
    monkeypatch.setattr(pilot_module, "time", fake)
    transport = _RecordingTransport(_valid_payload_text())
    client = build_pilot_client_chain(transport, min_interval_ms=500, max_requests=50)
    counting = client._inner  # noqa: SLF001 - same-package test wiring
    client.set_deadline(1000.4)

    client.complete("a")
    with pytest.raises(DeadlineExceeded):
        client.complete("b")

    assert transport.calls == 1
    assert counting.physical_dispatches == 1
    assert fake.sleeps == []


def test_success_after_retry_exact_counters(tmp_path: Path) -> None:
    """R1 acceptance 2: 1 evaluation, 3 logical attempts, 3 physical dispatches."""
    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:1]
    template = _write_template(tmp_path)
    transport = _FailCallsTransport({1, 2})
    client = build_pilot_client_chain(transport, min_interval_ms=0, max_requests=50)
    counting = client._inner  # noqa: SLF001 - same-package test wiring
    evaluator = LlmEvaluator(client=client, max_retries=2, enabled=True)
    result = run_llm_pilot(
        _pilot_config(template), evaluator, cases, tmp_path, tmp_path / "o-retry-ok"
    )

    assert result.evaluations_attempted == 1
    assert result.failed == 0 and result.successful == 1
    assert transport.calls == 3
    assert counting.physical_dispatches == 3
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["counters"]["physical_dispatches"] == 3
    assert result.counters["physical_dispatches"] == 3
    assert [o["status"] for o in _read_outcomes(result)] == ["success"]


def test_cap_mid_retry_exact_counters(tmp_path: Path) -> None:
    """R1 acceptance 3: refused reservation is not a physical dispatch."""
    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:1]
    template = _write_template(tmp_path)
    transport = _FailingTransport()
    client = build_pilot_client_chain(transport, min_interval_ms=0, max_requests=2)
    counting = client._inner  # noqa: SLF001 - same-package test wiring
    evaluator = LlmEvaluator(client=client, max_retries=5, enabled=True)
    result = run_llm_pilot(
        _pilot_config(template, max_requests=2), evaluator, cases, tmp_path, tmp_path / "o-cap"
    )

    # Two reservations succeeded (both timed out over the wire); the third
    # logical attempt was refused before any transport start.
    assert transport.calls == 2
    assert counting.physical_dispatches == 2
    assert counting.timeouts == 2 and counting.errors == 2
    assert result.evaluations_attempted == 1
    outcomes = _read_outcomes(result)
    assert len(outcomes) == 1
    assert outcomes[0]["status"] == "failed"
    assert outcomes[0]["error_kind"] == "budget"
    assert outcomes[0]["adapter_attempts"] == 3
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["counters"]["physical_dispatches"] == 2
    assert manifest["counters"]["timeouts"] == 2
    assert result.counters["physical_dispatches"] == 2


class _FakeHttpResponse:
    def __init__(self, payload_text: str) -> None:
        self._body = json.dumps({"choices": [{"message": {"content": payload_text}}]}).encode()

    def __enter__(self) -> _FakeHttpResponse:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._body)
        body, self._body = self._body[:size], self._body[size:]
        return body


def test_deadline_during_body_read_preserves_physical_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sloplab.experiments.pilot as pilot_module

    class _Socket:
        def __init__(self) -> None:
            self.timeouts: list[float] = []

        def settimeout(self, timeout: float) -> None:
            self.timeouts.append(timeout)

    class _StreamingResponse:
        def __init__(self, clock: FakeClock) -> None:
            self.body = b"x" * 128
            self.offset = 0
            self.clock = clock
            self.socket = _Socket()
            self.fp = type("File", (), {"raw": type("Raw", (), {"_sock": self.socket})()})()
            self.closed = False

        def __enter__(self) -> _StreamingResponse:
            return self

        def __exit__(self, *args: Any) -> None:
            self.closed = True

        def read1(self, size: int) -> bytes:
            self.clock.now += 0.03
            chunk = self.body[self.offset : self.offset + min(size, 8)]
            self.offset += len(chunk)
            return chunk

    clock = FakeClock(now=100.0)
    response = _StreamingResponse(clock)
    monkeypatch.setenv("DEADLINE_KEY", "test-key")
    monkeypatch.setattr(adapter_module, "time", clock)
    monkeypatch.setattr(pilot_module, "time", clock)
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *handlers: type(
            "Opener", (), {"open": staticmethod(lambda request, timeout=None: response)}
        )(),
    )

    transport = HttpLLMClient(
        model="m",
        api_key_env="DEADLINE_KEY",
        endpoint="https://example.invalid/v1",
        max_response_bytes=1024,
    )
    counting = CountingClient(transport, max_requests=1)
    throttled = ThrottledClient(counting, min_interval_ms=0)
    throttled.set_deadline(100.1)

    with pytest.raises(DeadlineExceeded) as caught:
        throttled.complete("prompt")

    assert caught.value.dispatch_started is True
    assert counting.physical_dispatches == 1
    assert counting.errors == 1
    assert throttled._last_dispatch == pytest.approx(100.0)  # noqa: SLF001
    assert response.closed is True
    assert response.socket.timeouts == pytest.approx([0.1, 0.07, 0.04, 0.01])


def test_http_deadline_bounds_urlopen_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """R1 acceptance 4: remaining run time caps the HTTP timeout (fake urlopen)."""
    monkeypatch.setenv("E2B_R1_API_KEY", "test-key-never-used")
    seen: dict[str, Any] = {}

    def _fake_urlopen(request: Any, timeout: Any = None) -> _FakeHttpResponse:
        seen["timeout"] = timeout
        _ = request
        return _FakeHttpResponse(_valid_payload_text())

    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *handlers: type("Opener", (), {"open": staticmethod(_fake_urlopen)})(),
    )
    fake = FakeClock(now=500.0)
    monkeypatch.setattr(adapter_module, "time", fake)

    client = HttpLLMClient(
        model="test-model",
        api_key_env="E2B_R1_API_KEY",
        endpoint="https://example.invalid/v1",
        timeout_s=60.0,
    )
    client.set_deadline(510.0)  # 10s remain: urlopen must see 10, not 60.
    response = client.complete("hello")
    assert seen["timeout"] == pytest.approx(10.0)
    assert json.loads(response.text)["decision"] == "accept"

    fake.now = 511.0  # deadline passed: no HTTP call at all.
    seen.clear()
    with pytest.raises(DeadlineExceeded):
        client.complete("hello")
    assert seen == {}

    client.set_deadline(None)  # no deadline: full configured timeout.
    client.complete("hello")
    assert seen["timeout"] == pytest.approx(60.0)


def test_long_retry_after_deadline_terminal_or_honored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R1 acceptance 5: long Retry-After refuses fast under deadline, else full."""
    import sloplab.experiments.pilot as pilot_module
    from sloplab.corpus.parser import parse_report
    from sloplab.models.evaluation import EvaluationContext

    fake = FakeClock(now=1000.0)
    monkeypatch.setattr(pilot_module, "time", fake)
    inner = _Once429ThenOk("9999")
    client = build_pilot_client_chain(inner, min_interval_ms=0, max_requests=50)
    counting = client._inner  # noqa: SLF001 - same-package test wiring
    client.set_deadline(1005.0)
    evaluator = LlmEvaluator(client=client, max_retries=3, enabled=True)
    doc = parse_report("# T\n\n## Summary\n\nBody.\n", fixture_id="x", path="x")
    with pytest.raises(EvaluationFailure) as exc_info:
        evaluator.evaluate(doc, EvaluationContext(report=doc, case_id="x", labels={}))
    # The 429 arrived over a real dispatch (physical == 1); the backoff wait
    # did not fit, so the failure is terminal deadline after 1 logical attempt.
    assert exc_info.value.error_kind == "deadline"
    assert exc_info.value.adapter_attempts == 1
    assert inner.calls == 1
    assert counting.physical_dispatches == 1
    assert fake.sleeps == []

    # Production path (no sleep cap, as llm_bench wires it): full wait honored.
    fake2 = FakeClock(now=2000.0)
    monkeypatch.setattr(pilot_module, "time", fake2)
    inner2 = _Once429ThenOk("120")
    client2 = build_pilot_client_chain(inner2, min_interval_ms=0, max_requests=50)
    evaluator2 = LlmEvaluator(client=client2, max_retries=1, enabled=True)
    result = evaluator2.evaluate(doc, EvaluationContext(report=doc, case_id="x", labels={}))
    assert result.decision.value == "accept"
    assert inner2.calls == 2
    assert fake2.sleeps == [pytest.approx(120.0)]
