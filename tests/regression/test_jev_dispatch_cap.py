"""A-004 acceptance 7: the physical dispatch cap holds, retries included.

``CountingTransport`` sits directly above the inner transport and below the
evaluator's retry loop, so with ``max_requests=N`` the (N+1)-th physical
dispatch is refused before the inner transport is called. No live calls: the
inner transport is a scripted fake and the socket guard is autouse.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest

from sloplab.evaluators.jev import CountingTransport, JevEvaluationFailure, JevEvaluator
from sloplab.evaluators.jev.failures import (
    BUDGET_EXCEEDED,
    TRANSPORT_RATE_LIMITED,
    TRANSPORT_TIMEOUT,
    BudgetExceeded,
    JevConfigError,
    JevRateLimited,
    JevTimeout,
)
from sloplab.evaluators.jev.transport import JevResponse
from tests._jev_fakes import (
    ScriptedTransport,
    block_network,
    make_context,
    make_report,
    recording_sleep,
    respond,
    valid_body,
)

MODEL = "typesafe/jev-1.13"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    block_network(monkeypatch)


def _evaluator(
    inner: Any, cap: int, *, max_retries: int = 1, max_wait_s: float = 60.0
) -> tuple[JevEvaluator, CountingTransport, list[float]]:
    waits, sleep = recording_sleep()
    counting = CountingTransport(inner, max_requests=cap)
    evaluator = JevEvaluator(
        counting, model_id=MODEL, max_retries=max_retries, max_wait_s=max_wait_s, sleep=sleep
    )
    return evaluator, counting, waits


@pytest.mark.parametrize("cap", [0, 1, 3])
def test_nth_plus_one_evaluation_never_dispatches(cap: int) -> None:
    inner = ScriptedTransport(respond(valid_body()), repeat_last=True)
    evaluator, counting, _ = _evaluator(inner, cap)
    for _ in range(cap):
        evaluator.evaluate(make_report(), make_context())
    with pytest.raises(JevEvaluationFailure) as info:
        evaluator.evaluate(make_report(), make_context())
    assert info.value.code == BUDGET_EXCEEDED
    assert inner.calls == cap
    assert counting.physical_dispatches == cap
    assert counting.counters.refused == 1


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (JevRateLimited(status=429, retry_after_s=0.0), TRANSPORT_RATE_LIMITED),
        (JevRateLimited(status=529, retry_after_s=None), TRANSPORT_RATE_LIMITED),
        (JevTimeout(), TRANSPORT_TIMEOUT),
    ],
)
def test_retries_are_counted_and_capped(error: BaseException, code: str) -> None:
    # Five retries allowed, but only two physical dispatches: the third attempt
    # is refused by the cap before reaching the inner transport.
    inner = ScriptedTransport(error, repeat_last=True)
    evaluator, counting, waits = _evaluator(inner, cap=2, max_retries=5)
    with pytest.raises(JevEvaluationFailure) as info:
        evaluator.evaluate(make_report(), make_context())
    assert info.value.code == BUDGET_EXCEEDED
    assert info.value.adapter_attempts == 3
    assert inner.calls == 2
    assert counting.physical_dispatches == 2
    assert counting.counters.errors == 2
    assert counting.counters.by_code == {code: 2}
    assert len(waits) == 2


def test_retry_then_success_counts_both_dispatches() -> None:
    inner = ScriptedTransport(JevRateLimited(status=429, retry_after_s=4.0), respond(valid_body()))
    evaluator, counting, waits = _evaluator(inner, cap=2, max_retries=1)
    result = evaluator.evaluate(make_report(), make_context())
    assert result.metadata["adapter_attempts"] == 2
    assert counting.physical_dispatches == 2
    assert waits == [4.0]  # Retry-After honored in full
    assert inner.bodies[0] == inner.bodies[1]  # every attempt sends the same body


def test_retry_after_above_wait_cap_is_not_shortened() -> None:
    inner = ScriptedTransport(JevRateLimited(status=429, retry_after_s=120.0), repeat_last=True)
    evaluator, counting, waits = _evaluator(inner, cap=5, max_retries=3, max_wait_s=30.0)
    with pytest.raises(JevEvaluationFailure) as info:
        evaluator.evaluate(make_report(), make_context())
    assert info.value.code == TRANSPORT_RATE_LIMITED
    assert waits == []
    assert inner.calls == 1
    assert counting.physical_dispatches == 1


def test_retry_allowance_exhausted_before_cap() -> None:
    inner = ScriptedTransport(JevTimeout(), repeat_last=True)
    evaluator, counting, _ = _evaluator(inner, cap=10, max_retries=2)
    with pytest.raises(JevEvaluationFailure) as info:
        evaluator.evaluate(make_report(), make_context())
    assert info.value.code == TRANSPORT_TIMEOUT
    assert info.value.adapter_attempts == 3
    assert counting.physical_dispatches == inner.calls == 3


def test_cap_holds_under_concurrency() -> None:
    cap = 7
    inner = ScriptedTransport(respond(valid_body()), repeat_last=True)
    counting = CountingTransport(inner, max_requests=cap)
    refused: list[int] = []
    lock = threading.Lock()
    barrier = threading.Barrier(16)

    def worker() -> None:
        barrier.wait()
        for _ in range(3):
            try:
                counting.decide({"model": MODEL})
            except BudgetExceeded:
                with lock:
                    refused.append(1)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert counting.physical_dispatches == cap
    assert inner.calls == cap
    assert len(refused) == 16 * 3 - cap


def test_errors_after_reservation_stay_counted() -> None:
    class _Boom:
        calls = 0

        def decide(self, body: dict[str, Any]) -> JevResponse:
            self.calls += 1
            raise RuntimeError("unexpected")

    inner = _Boom()
    counting = CountingTransport(inner, max_requests=2)
    with pytest.raises(RuntimeError):
        counting.decide({})
    assert counting.physical_dispatches == 1
    assert counting.remaining == 1


@pytest.mark.parametrize("cap", [-1, 1.5, True])
def test_invalid_cap_rejected(cap: Any) -> None:
    with pytest.raises(JevConfigError):
        CountingTransport(ScriptedTransport(), max_requests=cap)
