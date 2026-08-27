"""Asynchronous rate limiting and concurrency primitives for LLM evaluators."""

from __future__ import annotations

import asyncio
import time
from typing import Protocol

from sloplab.evaluators.llm.adapter import LLMResponse


class AsyncLLMClient(Protocol):
    """Protocol for asynchronous LLM clients."""

    async def complete_async(self, prompt: str) -> LLMResponse: ...  # pragma: no cover


class TokenBucketLimiter:
    """Thread-safe and async-safe token bucket rate limiter.

    Allows burst calls up to `capacity`, refilling at `rate_per_sec`.
    """

    def __init__(self, rate_per_sec: float, capacity: float | None = None) -> None:
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be positive")
        self.rate = rate_per_sec
        self.capacity = capacity if capacity is not None else rate_per_sec
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        """Wait until enough tokens are available in the bucket."""
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                # Calculate sleep duration until next token
                needed = tokens - self.tokens
                wait_time = needed / self.rate

            await asyncio.sleep(wait_time)


class ThrottledAsyncClient:
    """Wraps an AsyncLLMClient with token bucket rate limiting and concurrency semaphores."""

    def __init__(
        self,
        inner: AsyncLLMClient,
        *,
        rate_per_sec: float = 10.0,
        max_concurrent: int = 4,
    ) -> None:
        self._inner = inner
        self._limiter = TokenBucketLimiter(rate_per_sec=rate_per_sec)
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def complete_async(self, prompt: str) -> LLMResponse:
        await self._limiter.acquire(1.0)
        async with self._semaphore:
            return await self._inner.complete_async(prompt)
