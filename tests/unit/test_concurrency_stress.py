"""Stress tests and edge cases for concurrent evaluation and async rate limiters."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sloplab.evaluators.base import get_evaluator
from sloplab.evaluators.llm.adapter import LLMResponse
from sloplab.evaluators.llm.rate_limit import (
    AsyncLLMClient,
    ThrottledAsyncClient,
    TokenBucketLimiter,
)
from sloplab.scoring.harness import run_suite

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_token_bucket_limiter_invalid_rate() -> None:
    with pytest.raises(ValueError, match="rate_per_sec must be positive"):
        TokenBucketLimiter(rate_per_sec=0.0)
    with pytest.raises(ValueError, match="rate_per_sec must be positive"):
        TokenBucketLimiter(rate_per_sec=-5.0)


def test_token_bucket_limiter_zero_tokens() -> None:
    async def _run() -> None:
        limiter = TokenBucketLimiter(rate_per_sec=10.0)
        # Requesting 0 tokens should complete immediately
        await limiter.acquire(0.0)

    asyncio.run(_run())


def test_run_suite_zero_or_negative_concurrency() -> None:
    evaluator = get_evaluator("rules-baseline")
    # Empty cases list with concurrency <= 0
    assert run_suite(evaluator, [], concurrency=0) == []
    assert run_suite(evaluator, [], concurrency=-2) == []


def test_throttled_async_client_stress() -> None:
    async def _run() -> None:
        call_count = 0

        class FastMockClient(AsyncLLMClient):
            async def complete_async(self, prompt: str) -> LLMResponse:
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.01)
                return LLMResponse(text='{"decision": "reject"}', latency_ms=10)

        client = ThrottledAsyncClient(FastMockClient(), rate_per_sec=200.0, max_concurrent=5)
        tasks = [client.complete_async(f"prompt-{i}") for i in range(25)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 25
        assert call_count == 25
        assert all(r.text == '{"decision": "reject"}' for r in results)

    asyncio.run(_run())
