"""Tests for concurrent evaluation and asynchronous rate limiting (Phase 6)."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from sloplab.evaluators.base import get_evaluator
from sloplab.evaluators.llm.adapter import LLMResponse
from sloplab.evaluators.llm.rate_limit import (
    AsyncLLMClient,
    ThrottledAsyncClient,
    TokenBucketLimiter,
)
from sloplab.scoring.harness import build_cases, run_suite

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_token_bucket_limiter_acquires_tokens() -> None:
    async def _run() -> None:
        limiter = TokenBucketLimiter(rate_per_sec=100.0, capacity=10.0)
        # Burst 5 tokens instantly
        t0 = time.monotonic()
        for _ in range(5):
            await limiter.acquire(1.0)
        duration = time.monotonic() - t0
        assert duration < 0.1

    asyncio.run(_run())


def test_throttled_async_client_limits_concurrency() -> None:
    async def _run() -> None:
        active_concurrent = 0
        max_observed_concurrent = 0

        class MockAsyncClient(AsyncLLMClient):
            async def complete_async(self, prompt: str) -> LLMResponse:
                nonlocal active_concurrent, max_observed_concurrent
                active_concurrent += 1
                max_observed_concurrent = max(max_observed_concurrent, active_concurrent)
                await asyncio.sleep(0.05)
                active_concurrent -= 1
                return LLMResponse(text='{"decision": "accept"}', latency_ms=50)

        client = ThrottledAsyncClient(MockAsyncClient(), rate_per_sec=50.0, max_concurrent=2)

        tasks = [client.complete_async(f"prompt-{i}") for i in range(6)]
        responses = await asyncio.gather(*tasks)

        assert len(responses) == 6
        assert max_observed_concurrent <= 2

    asyncio.run(_run())


def test_run_suite_concurrency_deterministic_equivalence() -> None:
    """Concurrent execution must produce byte/field identical results to sequential execution."""
    suite_index = REPO_ROOT / "benchmarks/results/v1-core-example/suite-index.jsonl"
    corpus_root = REPO_ROOT / "corpus"
    materialized_root = REPO_ROOT / "benchmarks/results/v1-core-example"

    all_cases = build_cases(suite_index, corpus_root, materialized_root)
    # Take first 12 cases for speed
    cases = all_cases[:12]

    evaluator = get_evaluator("rules-baseline")

    # Sequential run
    seq_records = run_suite(evaluator, cases, concurrency=1)

    # Parallel run with 4 workers
    par_records = run_suite(evaluator, cases, concurrency=4)

    assert len(seq_records) == len(par_records) == len(cases)

    for seq, par in zip(seq_records, par_records, strict=True):
        assert seq.case_id == par.case_id
        assert seq.decision == par.decision
        assert seq.confidence == pytest.approx(par.confidence)
        assert seq.expected_decision == par.expected_decision
        assert seq.findings == par.findings
        assert seq.rationale == par.rationale
