"""Mock-based tests for the budgeted LLM pilot runner (V27). No live calls."""

from __future__ import annotations

import email.utils
import json
from pathlib import Path
from typing import Any

import pytest

from sloplab.evaluators.llm.adapter import LlmEvaluator, LLMResponse
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.pilot import CountingClient, ThrottledClient, run_llm_pilot
from sloplab.experiments.runner import load_pilot_config
from sloplab.scoring.harness import build_cases

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT_CONFIG = REPO_ROOT / "experiments/configs/llm-pilot-v0.2.yaml"

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


class StaticResponder:
    """Transport double returning a fixed valid payload."""

    def __init__(self, payload_text: str) -> None:
        self.payload_text = payload_text

    def complete(self, prompt: str) -> Any:
        _ = prompt

        class _R:
            text = self.payload_text
            latency_ms = 1

        return _R()


class TimeoutResponder:
    def complete(self, prompt: str) -> Any:
        raise TimeoutError("simulated timeout")


def canonical_cases(n: int) -> list[Any]:
    example_dir = REPO_ROOT / "benchmarks/results/v1-core-example"
    cases = build_cases(
        example_dir / "suite-index.jsonl",
        REPO_ROOT / "corpus",
        example_dir,
    )
    return [c for c in cases if c.kind == "canonical"][:n]


def make_evaluator(inner: Any, max_requests: int = 1000) -> tuple[LlmEvaluator, CountingClient]:
    client = CountingClient(inner, max_requests)
    evaluator = LlmEvaluator(client=client, max_retries=0, enabled=True)
    return evaluator, client


class TestBudgetEnforcement:
    def test_budget_stops_dispatch_and_counts_skips(self, tmp_path: Path) -> None:
        config: LLMPilotConfig = load_pilot_config(PILOT_CONFIG)
        config.max_cases = 2
        config.repeats = 3

        evaluator, client = make_evaluator(StaticResponder(VALID_PAYLOAD), max_requests=4)
        result = run_llm_pilot(config, evaluator, canonical_cases(2), REPO_ROOT, tmp_path / "out")
        assert client.requests == 4
        assert result.skipped_by_budget > 0
        assert result.counters["requests"] == 4
        # 2 cases in repeat 1 (budget 4 -> 2 requests each? no: 1 request per case)
        assert len(json.loads("[]")) == 0  # sanity no-op

    def test_full_pilot_within_budget_is_stable(self, tmp_path: Path) -> None:
        config: LLMPilotConfig = load_pilot_config(PILOT_CONFIG)
        config.max_cases = 1
        repeats = config.repeats

        evaluator, client = make_evaluator(StaticResponder(VALID_PAYLOAD))
        result = run_llm_pilot(config, evaluator, canonical_cases(1), REPO_ROOT, tmp_path / "o")
        assert result.evaluations_attempted == repeats
        assert result.failed_evaluations == 0
        assert client.requests == repeats
        manifest = json.loads(result.manifest_path.read_text())
        assert manifest["stability"]["unanimous_cases"] == 1
        assert manifest["prompt_hash"]


class TestFailureAccounting:
    def test_timeouts_become_failed_records_and_are_counted(self, tmp_path: Path) -> None:
        config: LLMPilotConfig = load_pilot_config(PILOT_CONFIG)
        config.max_cases = 1
        counting = CountingClient(TimeoutResponder(), max_requests=10)
        evaluator = LlmEvaluator(client=counting, max_retries=1, enabled=True)

        result = run_llm_pilot(config, evaluator, canonical_cases(1), REPO_ROOT, tmp_path / "o")
        assert result.counters["timeouts"] >= 1
        records = [json.loads(line) for line in result.records_path.read_text().splitlines()]
        assert records and all(r["evaluation_metadata"].get("failed") for r in records)


# ---------------------------------------------------------------------------
# Pacing (min_interval_ms) and HTTP 429 Retry-After handling
# ---------------------------------------------------------------------------


class FakeTime:
    """Deterministic clock replacing ``time`` inside the pilot module."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class DispatchCounter:
    """Inner transport recording dispatches; optionally raises a canned error."""

    def __init__(self, fail_times: int = 0, error: Exception | None = None) -> None:
        self.calls = 0
        self.fail_times = fail_times
        self.error = error

    def complete(self, prompt: str) -> Any:
        _ = prompt
        self.calls += 1
        if self.calls <= self.fail_times and self.error is not None:
            raise self.error
        return LLMResponse(text=VALID_PAYLOAD, latency_ms=1)


class Http429(Exception):
    """Stand-in for urllib.error.HTTPError carrying status code and headers."""

    def __init__(self, retry_after: str | None) -> None:
        super().__init__("too many requests")
        self.code = 429
        self.headers = {"Retry-After": retry_after} if retry_after else {}


def test_throttle_sleeps_between_dispatches(monkeypatch: Any) -> None:
    fake_time = FakeTime()
    monkeypatch.setattr("sloplab.experiments.pilot.time", fake_time)
    inner = DispatchCounter()
    client = ThrottledClient(inner, min_interval_ms=500)

    client.complete("a")
    client.complete("b")
    client.complete("c")

    assert inner.calls == 3
    # First dispatch is free; each subsequent one waits out the interval.
    assert fake_time.sleeps == [pytest.approx(0.5), pytest.approx(0.5)]


def test_throttle_zero_interval_never_sleeps(monkeypatch: Any) -> None:
    fake_time = FakeTime()
    monkeypatch.setattr("sloplab.experiments.pilot.time", fake_time)
    inner = DispatchCounter()
    client = ThrottledClient(inner, min_interval_ms=0)
    for _ in range(3):
        client.complete("x")
    assert inner.calls == 3 and fake_time.sleeps == []


def test_429_retry_after_is_honored_then_reraised(monkeypatch: Any) -> None:
    fake_time = FakeTime()
    monkeypatch.setattr("sloplab.experiments.pilot.time", fake_time)
    inner = DispatchCounter(fail_times=1, error=Http429(retry_after="7"))
    client = ThrottledClient(inner, min_interval_ms=0)

    with pytest.raises(Http429):
        client.complete("x")

    assert inner.calls == 1
    assert fake_time.sleeps == [pytest.approx(7.0)]
    # Second attempt succeeds after honoring the wait.
    response = client.complete("x")
    assert response.text == VALID_PAYLOAD


def test_429_http_date_retry_after(monkeypatch: Any) -> None:
    fake_time = FakeTime()
    monkeypatch.setattr("sloplab.experiments.pilot.time", fake_time)
    when = email.utils.formatdate(fake_time.time() + 9, usegmt=True)
    inner = DispatchCounter(fail_times=1, error=Http429(retry_after=when))
    client = ThrottledClient(inner, min_interval_ms=0)

    with pytest.raises(Http429):
        client.complete("x")
    assert fake_time.sleeps == [pytest.approx(9.0, abs=1.0)]


def test_429_without_header_raises_without_extra_sleep(monkeypatch: Any) -> None:
    fake_time = FakeTime()
    monkeypatch.setattr("sloplab.experiments.pilot.time", fake_time)
    inner = DispatchCounter(fail_times=1, error=Http429(retry_after=None))
    client = ThrottledClient(inner, min_interval_ms=0)

    with pytest.raises(Http429):
        client.complete("x")
    assert inner.calls == 1 and fake_time.sleeps == []


def test_429_infinite_retry_after_is_ignored_not_honored(monkeypatch: Any) -> None:
    """A hostile `Retry-After: inf` must never hang the run (P3)."""
    fake_time = FakeTime()
    monkeypatch.setattr("sloplab.experiments.pilot.time", fake_time)
    for bad in ("inf", "-inf", "nan"):
        inner = DispatchCounter(fail_times=1, error=Http429(retry_after=bad))
        client = ThrottledClient(inner, min_interval_ms=0)
        with pytest.raises(Http429):
            client.complete("x")
        assert inner.calls == 1
        assert fake_time.sleeps == [], f"non-finite {bad!r} must not sleep"
        fake_time.sleeps.clear()


def test_non_429_errors_get_no_retry_after_sleep(monkeypatch: Any) -> None:
    fake_time = FakeTime()
    monkeypatch.setattr("sloplab.experiments.pilot.time", fake_time)
    inner = DispatchCounter(fail_times=1, error=TimeoutError("boom"))
    client = ThrottledClient(inner, min_interval_ms=250)

    with pytest.raises(TimeoutError):
        client.complete("x")
    assert inner.calls == 1 and fake_time.sleeps == []


def test_sleep_cap_bounds_long_retry_after(monkeypatch: Any) -> None:
    fake_time = FakeTime()
    monkeypatch.setattr("sloplab.experiments.pilot.time", fake_time)
    inner = DispatchCounter(fail_times=1, error=Http429(retry_after="9999"))
    client = ThrottledClient(inner, min_interval_ms=0, sleep_cap_s=3.0)

    with pytest.raises(Http429):
        client.complete("x")
    assert fake_time.sleeps == [pytest.approx(3.0)]
