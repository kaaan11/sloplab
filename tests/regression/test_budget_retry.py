"""E2b: single budget owner, retry/deadline policy, repeat coverage. No live calls."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from sloplab.corpus.loader import discover_fixtures
from sloplab.evaluators.llm.adapter import LlmEvaluator, LLMResponse, PromptTemplateError
from sloplab.evaluators.llm.failures import (
    BudgetExhausted,
    DeadlineExceeded,
    EvaluationFailure,
    classify_dispatch_error,
)
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.pilot import (
    CountingClient,
    ThrottledClient,
    build_pilot_client_chain,
    check_outcome_coverage,
    run_llm_pilot,
)
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import materialize_suite
from sloplab.scoring.harness import build_cases
from tests._helpers import write_canonical_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "llm_bench_e2b", REPO_ROOT / "scripts" / "llm_bench.py"
)
assert _spec is not None and _spec.loader is not None
llm_bench: ModuleType = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(llm_bench)


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
        self.prompts: list[str] = []
        self.calls = 0

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        self.prompts.append(prompt)
        return LLMResponse(text=self.payload_text, latency_ms=1)


class _FailCallsTransport(_RecordingTransport):
    """Fails exactly the given 1-indexed dispatch numbers with a timeout."""

    def __init__(self, fail_calls: set[int]) -> None:
        super().__init__(_valid_payload_text())
        self.fail_calls = fail_calls

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        self.prompts.append(prompt)
        if self.calls in self.fail_calls:
            raise TimeoutError("simulated timeout")
        return LLMResponse(text=self.payload_text, latency_ms=1)


class _FailingTransport(_RecordingTransport):
    def __init__(self) -> None:
        super().__init__(_valid_payload_text())

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        self.prompts.append(prompt)
        raise TimeoutError("simulated outage")


class _Http429(Exception):
    def __init__(self, retry_after: str) -> None:
        super().__init__("too many requests")
        self.code = 429
        self.headers = {"Retry-After": retry_after}


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


class ScriptedClock(FakeClock):
    """Monotonic returns scripted values in order; extras raise loudly."""

    def __init__(self, values: list[float]) -> None:
        super().__init__(now=values[0], advance_on_sleep=False)
        self.values = list(values)

    def monotonic(self) -> float:
        if not self.values:
            raise AssertionError("monotonic called more often than scripted")
        return self.values.pop(0)


def _workspace(tmp_path: Path) -> dict[str, Any]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Budget clean report",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "b-000",
        fixture_id="canonical-b-000",
        title="Budget second report",
        report_class="valid",
    )
    suite = {
        "name": "budget-suite",
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
    path = tmp_path / "triage-e2b.md"
    path.write_text("Route carefully. E2B-MARKER\n\n{report_text}\n", encoding="utf-8")
    return path


def _pilot_config(
    prompt_file: Path,
    max_requests: int = 50,
    repeats: int = 1,
    deadline_s: float | None = None,
    min_interval_ms: int = 0,
) -> LLMPilotConfig:
    budget: dict[str, Any] = {"max_requests": max_requests, "min_interval_ms": min_interval_ms}
    if deadline_s is not None:
        budget["deadline_s"] = deadline_s
    return LLMPilotConfig.model_validate(
        {
            "schema_version": 2,
            "name": "budget-pilot",
            "suite": {"config_path": "benchmarks/suites/v1-core.yaml", "corpus_root": "corpus"},
            "base_seed": 21,
            "repeats": repeats,
            "model_env": "E2B_MODEL",
            "endpoint_env": "E2B_ENDPOINT",
            "api_key_env": "E2B_API_KEY",
            "prompt_file": str(prompt_file),
            "budget": budget,
            "case_selection": "canonical_first",
            "max_cases": None,
        }
    )


def _run_pilot(
    tmp_path: Path,
    prompt_file: Path,
    cases: list[Any],
    transport: Any,
    max_retries: int = 0,
    repeats: int = 1,
    max_requests: int = 50,
    deadline_s: float | None = None,
    min_interval_ms: int = 0,
    out_name: str = "pilot-out",
) -> Any:
    client = build_pilot_client_chain(
        transport, min_interval_ms=min_interval_ms, max_requests=max_requests
    )
    evaluator = LlmEvaluator(client=client, max_retries=max_retries, enabled=True)
    return run_llm_pilot(
        _pilot_config(
            prompt_file,
            max_requests=max_requests,
            repeats=repeats,
            deadline_s=deadline_s,
            min_interval_ms=min_interval_ms,
        ),
        evaluator,
        cases,
        tmp_path,
        tmp_path / out_name,
    )


def _read_outcomes(result: Any) -> list[dict[str, Any]]:
    assert result.outcomes_path is not None
    return [
        json.loads(line)
        for line in result.outcomes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_records(result: Any) -> list[dict[str, Any]]:
    text = result.records_path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_physical_dispatches_never_exceed_cap(tmp_path: Path) -> None:
    """Gate holds on direct use, cap 0, and mid-retry exhaustion."""
    inner_calls = 0

    class _Inner:
        def complete(self, prompt: str) -> Any:
            nonlocal inner_calls
            _ = prompt
            inner_calls += 1
            return LLMResponse(text=_valid_payload_text(), latency_ms=1)

    client = CountingClient(_Inner(), max_requests=2)
    client.complete("a")
    client.complete("b")
    with pytest.raises(BudgetExhausted):
        client.complete("c")
    assert inner_calls == 2

    empty = CountingClient(_Inner(), max_requests=0)
    with pytest.raises(BudgetExhausted):
        empty.complete("a")
    assert inner_calls == 2

    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:1]
    template = _write_template(tmp_path)
    failing = _FailingTransport()
    result = _run_pilot(tmp_path, template, cases, failing, max_retries=5, max_requests=2)
    assert failing.calls == 2
    outcomes = _read_outcomes(result)
    assert len(outcomes) == 1 and outcomes[0]["status"] == "failed"
    assert outcomes[0]["error_kind"] == "budget"
    assert outcomes[0]["adapter_attempts"] == 3

    failing2 = _FailingTransport()
    result2 = _run_pilot(tmp_path, template, cases, failing2, max_retries=5, max_requests=1)
    assert failing2.calls == 1
    outcomes2 = _read_outcomes(result2)
    assert outcomes2[0]["error_kind"] == "budget"
    assert outcomes2[0]["adapter_attempts"] == 2


def test_terminal_parse_and_config_never_retry(tmp_path: Path) -> None:
    """Parse/config defects are terminal; timeout/transport/429 follow retries."""
    from sloplab.corpus.parser import parse_report
    from sloplab.models.evaluation import EvaluationContext

    doc = parse_report("# T\n\n## Summary\n\nBody.\n", fixture_id="x", path="x")
    bad = _RecordingTransport("definitely not json {{{")
    evaluator = LlmEvaluator(
        client=CountingClient(bad, max_requests=50), max_retries=3, enabled=True
    )
    with pytest.raises(EvaluationFailure) as exc_info:
        evaluator.evaluate(doc, EvaluationContext(report=doc, case_id="x", labels={}))
    assert exc_info.value.error_kind == "parse"
    assert bad.calls == 1

    paths = _workspace(tmp_path)
    boom = _RecordingTransport(_valid_payload_text())
    with pytest.raises(PromptTemplateError, match="does-not-exist"):
        _run_pilot(tmp_path, tmp_path / "does-not-exist.md", paths["cases"][:1], boom)
    assert boom.calls == 0

    flaky = _FailCallsTransport({1})
    ok_evaluator = LlmEvaluator(
        client=CountingClient(flaky, max_requests=50), max_retries=1, enabled=True
    )
    result = ok_evaluator.evaluate(doc, EvaluationContext(report=doc, case_id="x", labels={}))
    assert flaky.calls == 2
    assert result.decision.value == "accept"

    rl = _RateLimited()
    rl_evaluator = LlmEvaluator(
        client=CountingClient(rl, max_requests=50), max_retries=1, enabled=True
    )
    rl_result = rl_evaluator.evaluate(doc, EvaluationContext(report=doc, case_id="x", labels={}))
    assert rl.calls == 2
    assert rl_result.decision.value == "accept"

    rl_always = _RateLimitedAlways()
    rl_evaluator2 = LlmEvaluator(
        client=CountingClient(rl_always, max_requests=50), max_retries=1, enabled=True
    )
    with pytest.raises(EvaluationFailure) as exc_info2:
        rl_evaluator2.evaluate(doc, EvaluationContext(report=doc, case_id="x", labels={}))
    assert exc_info2.value.error_kind == "rate-limit"
    assert exc_info2.value.adapter_attempts == 2

    assert classify_dispatch_error(TimeoutError("t")) == ("timeout", "transport.timeout", True)
    assert classify_dispatch_error(ConnectionError("c")) == ("transport", "transport.error", True)
    assert classify_dispatch_error(BudgetExhausted("x")) == ("budget", "budget.exhausted", False)


class _Http429Local(Exception):
    def __init__(self, retry_after: str) -> None:
        super().__init__("too many requests")
        self.code = 429
        self.headers = {"Retry-After": retry_after}


class _RateLimited:
    """Fails the first dispatch with 429, then succeeds."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        _ = prompt
        if self.calls == 1:
            raise _Http429Local("120")
        return LLMResponse(text=_valid_payload_text(), latency_ms=1)


class _RateLimitedAlways:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt: str) -> Any:
        self.calls += 1
        _ = prompt
        raise _Http429Local("120")


def test_clock_contracts_are_separate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Timeout, deadline, pacing, and Retry-After behave independently (fake clock)."""
    import sloplab.experiments.pilot as pilot_module

    fake = FakeClock(now=1000.0)
    monkeypatch.setattr(pilot_module, "time", fake)
    inner = _FailCallsTransport(set())
    client = ThrottledClient(inner, min_interval_ms=500)
    client.complete("a")
    client.complete("b")
    client.complete("c")
    assert inner.calls == 3
    assert fake.sleeps == [pytest.approx(0.5), pytest.approx(0.5)]

    fake2 = FakeClock(now=2000.0)
    monkeypatch.setattr(pilot_module, "time", fake2)
    inner2 = _FailCallsTransport(set())
    client2 = ThrottledClient(inner2, min_interval_ms=500, deadline_monotonic=2000.4)
    client2.complete("a")
    with pytest.raises(DeadlineExceeded):
        client2.complete("b")
    assert inner2.calls == 1
    assert fake2.sleeps == []

    fake3 = FakeClock(now=3000.0)
    monkeypatch.setattr(pilot_module, "time", fake3)

    class _Once429:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, prompt: str) -> Any:
            self.calls += 1
            _ = prompt
            if self.calls == 1:
                raise _Http429Local("7")
            return LLMResponse(text=_valid_payload_text(), latency_ms=1)

    inner3 = _Once429()
    client3 = ThrottledClient(inner3, min_interval_ms=0)
    with pytest.raises(_Http429Local):
        client3.complete("x")
    assert fake3.sleeps == [pytest.approx(7.0)]
    client3.complete("x")
    assert inner3.calls == 2


def test_oversized_wait_is_terminal_without_hanging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deadline-blocked waits refuse fast: failed for started plans, not_run before."""
    import sloplab.experiments.pilot as pilot_module

    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:2]
    template = _write_template(tmp_path)

    fake = FakeClock(now=1000.0)
    monkeypatch.setattr(pilot_module, "time", fake)
    transport = _RecordingTransport(_valid_payload_text())
    client = build_pilot_client_chain(transport, min_interval_ms=3600000, max_requests=50)
    counting = client._inner  # noqa: SLF001 - same-package test wiring
    evaluator = LlmEvaluator(client=client, max_retries=0, enabled=True)
    result = run_llm_pilot(
        _pilot_config(template, min_interval_ms=3600000, deadline_s=60.0),
        evaluator,
        cases,
        tmp_path,
        tmp_path / "o-deadline-wait",
    )
    outcomes = _read_outcomes(result)
    assert [o["status"] for o in outcomes] == ["success", "failed"]
    failed = outcomes[1]
    assert failed["error_kind"] == "deadline"
    assert "decision" not in failed
    assert fake.sleeps == []
    # Reviewer counterexample: the refused pacing wait consumed nothing.
    assert transport.calls == 1
    assert counting.physical_dispatches == 1

    clock2 = ScriptedClock([5000.0, 6000.0])
    monkeypatch.setattr(pilot_module, "time", clock2)
    transport2 = _RecordingTransport(_valid_payload_text())
    result2 = _run_pilot(
        tmp_path,
        template,
        cases[:1],
        transport2,
        repeats=2,
        deadline_s=60.0,
        out_name="o-deadline-pre",
    )
    assert transport2.calls == 0
    outcomes2 = _read_outcomes(result2)
    assert len(outcomes2) == 2
    assert all(o["status"] == "not_run" and o["reason"] == "deadline_exceeded" for o in outcomes2)
    manifest2 = json.loads(result2.manifest_path.read_text(encoding="utf-8"))
    assert manifest2["not_run"] == 2


def test_ledger_counters_reconcile(tmp_path: Path) -> None:
    """planned/dispatched/physical/scored reconcile across mixed outcomes."""
    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:2]
    template = _write_template(tmp_path)
    result = _run_pilot(tmp_path, template, cases, _FailingTransport(), repeats=2, max_requests=3)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert (
        manifest["planned"],
        manifest["successful"],
        manifest["failed"],
        manifest["not_run"],
        manifest["scored"],
    ) == (4, 0, 3, 1, 0)
    dispatched = manifest["successful"] + manifest["failed"]
    assert result.evaluations_attempted == dispatched == 3
    assert manifest["counters"]["physical_dispatches"] == 3
    assert _read_records(result) == []
    outcomes = _read_outcomes(result)
    assert sum(o["adapter_attempts"] for o in outcomes if o["status"] == "failed") == 3
    expected_keys = {(c.case_id, "llm-json", r) for r in range(2) for c in cases}
    assert {
        (o["case_id"], o["evaluator_name"], o["repeat_index"]) for o in outcomes
    } == expected_keys


def test_coverage_gate_and_checker(tmp_path: Path) -> None:
    """Missing/duplicate/foreign outcomes are coverage errors; full success is stable."""

    def _row(case_id: str, repeat: int, status: str = "success") -> dict[str, Any]:
        row: dict[str, Any] = {
            "schema_version": 1,
            "status": status,
            "case_id": case_id,
            "evaluator_name": "llm-json",
            "repeat_index": repeat,
        }
        if status == "success":
            row["record_ref"] = {"case_id": case_id, "repeat_index": repeat}
        return row

    base = [_row("c1", 0), _row("c1", 1), _row("c2", 0), _row("c2", 1)]
    assert (
        check_outcome_coverage(base, case_ids=["c1", "c2"], evaluator_name="llm-json", repeats=2)
        == []
    )
    assert any(
        "missing" in e
        for e in check_outcome_coverage(
            base[:-1], case_ids=["c1", "c2"], evaluator_name="llm-json", repeats=2
        )
    )
    assert any(
        "duplicate" in e
        for e in check_outcome_coverage(
            [*base, base[0]], case_ids=["c1", "c2"], evaluator_name="llm-json", repeats=2
        )
    )
    assert any(
        "foreign" in e
        for e in check_outcome_coverage(
            [*base, _row("cx", 0)], case_ids=["c1", "c2"], evaluator_name="llm-json", repeats=2
        )
    )
    assert any(
        "malformed" in e
        for e in check_outcome_coverage(
            [{"status": "success"}], case_ids=["c1"], evaluator_name="llm-json", repeats=1
        )
    )

    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:1]
    template = _write_template(tmp_path)
    full = _run_pilot(
        tmp_path,
        template,
        cases,
        _RecordingTransport(_valid_payload_text()),
        repeats=3,
        out_name="o-full",
    )
    assert full.stability.get("unanimous_cases") == 1
    full_manifest = json.loads(full.manifest_path.read_text(encoding="utf-8"))
    assert full_manifest["coverage"] == {"expected": 3, "successful": 3, "complete": True}
    assert full_manifest["stability_omitted_reason"] is None

    partial = _run_pilot(
        tmp_path, template, cases, _FailCallsTransport({2}), repeats=3, out_name="o-partial"
    )
    assert partial.stability == {}
    partial_manifest = json.loads(partial.manifest_path.read_text(encoding="utf-8"))
    assert partial_manifest["stability_omitted_reason"] == "incomplete-success-coverage"
    assert partial_manifest["coverage"] == {"expected": 3, "successful": 2, "complete": False}


def test_script_uses_same_ledger_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    """Script output is ledger-driven: mixed states print, counts reconcile."""
    monkeypatch.setenv("SLOPLAB_LLM_MODEL", "openai/gpt-oss-20b:free")
    monkeypatch.setenv("SLOPLAB_LLM_ENDPOINT", "https://example.invalid/v1")
    monkeypatch.setenv("SLOPLAB_LLM_API_KEY", "test-key-never-logged")

    transport = _FailCallsTransport({2, 3, 4})

    class _ScriptFake:
        def __init__(self, **kwargs: Any) -> None:
            _ = kwargs

        def complete(self, prompt: str) -> LLMResponse:
            transport.calls += 1
            transport.prompts.append(prompt)
            if transport.calls in transport.fail_calls:
                raise TimeoutError("simulated timeout")
            return LLMResponse(text=_valid_payload_text(), latency_ms=1)

    monkeypatch.setattr(llm_bench, "HttpLLMClient", _ScriptFake)
    config = tmp_path / "e2b-pilot.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "name": "e2b-pilot",
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
        ["--config", str(config), "--max-cases", "2", "--repeats", "1", "--out", str(out)]
    )
    assert rc == 1
    bundle = tmp_path / "llm-bench-results.bundle"
    outcomes = [
        json.loads(line)
        for line in (bundle / "outcomes.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [o["status"] for o in outcomes] == ["success", "failed"]
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["planned"] == manifest["successful"] + manifest["failed"] + manifest["not_run"]
    printed = capsys.readouterr().out
    assert "FAILED-EVAL (timeout)" in printed
    assert "failed evaluations: 1/2" in printed
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
