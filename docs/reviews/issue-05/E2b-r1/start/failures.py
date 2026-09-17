"""Typed evaluation failures shared by the LLM adapter, harness, and pilot (E2a).

An operational failure (unparseable response, timeout, transport error, spent
budget) is an exception, never a triage decision. :class:`EvaluationFailure`
carries the error kind, the logical adapter attempt count, and the rendered
prompt identity — never a decision, confidence, or dimensions.

``adapter_attempts`` counts logical adapter attempts (1 + retries consumed), not
physical dispatches; the physical budget accounting stays with the pilot's
counting client (centralized in E2b). ``detail`` is a short controlled
description: no raw model responses, full prompts, credentials, or unchecked
exception dumps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sloplab.models.evaluation import EvaluationResult

#: Known error kinds. ``legacy`` marks pre-E2a failed placeholders converted at
#: an outcome boundary; it carries no measured attempt count semantics beyond
#: one observed evaluation call. ``rate-limit`` marks explicit HTTP 429 /
#: provider backpressure (retriable); ``deadline`` marks waits or dispatches
#: refused by the run's monotonic deadline (terminal).
ERROR_KINDS = ("parse", "timeout", "transport", "budget", "legacy", "rate-limit", "deadline")


class BudgetExhausted(Exception):
    """Raised when the configured request budget is spent (physical cap)."""


class DeadlineExceeded(Exception):
    """Raised instead of sleeping when a required wait does not fit the deadline."""


def classify_dispatch_error(exc: BaseException) -> tuple[str, str, bool]:
    """Map a dispatch error to ``(error_kind, detail_code, retriable)``.

    Terminal (never retried): spent budget and deadline refusal — retrying
    cannot succeed. Retriable: timeouts, transports, and explicit 429 /
    provider backpressure. Detail codes are stable strings; exception text
    (which may carry credentials, URLs, or raw responses) is never copied.
    """
    if isinstance(exc, BudgetExhausted):
        return ("budget", "budget.exhausted", False)
    if isinstance(exc, DeadlineExceeded):
        return ("deadline", "deadline.exceeded", False)
    if getattr(exc, "code", None) == 429:
        return ("rate-limit", "rate_limited", True)
    if isinstance(exc, TimeoutError):
        return ("timeout", "transport.timeout", True)
    return ("transport", "transport.error", True)


@dataclass(frozen=True)
class EvaluationFailure(Exception):
    """Typed operational failure; never a scoring observation."""

    error_kind: str
    adapter_attempts: int
    rendered_prompt_hash: str
    detail: str

    def __str__(self) -> str:
        return f"{self.error_kind} after {self.adapter_attempts} attempt(s): {self.detail}"


def failure_from_legacy_result(result: EvaluationResult) -> EvaluationFailure:
    """Convert a legacy failed placeholder into a typed failure.

    Legacy placeholders record no decision, so they must not become success
    records. The rendered hash is preserved when the placeholder carries one;
    otherwise it stays empty (unknown, not recomputed here).
    """
    metadata: dict[str, Any] = result.metadata or {}
    rendered = metadata.get("rendered_prompt_hash")
    return EvaluationFailure(
        error_kind="legacy",
        adapter_attempts=1,
        rendered_prompt_hash=rendered if isinstance(rendered, str) else "",
        detail="legacy failed placeholder; no decision recorded",
    )


def raise_if_failed_result(result: EvaluationResult) -> EvaluationResult:
    """Pass ``result`` through, raising for legacy failed placeholders.

    Only an explicit ``failed=True`` marker triggers conversion; ordinary
    results (including ones without any ``failed`` key) pass untouched.
    """
    if result.metadata.get("failed") is True:
        raise failure_from_legacy_result(result)
    return result
