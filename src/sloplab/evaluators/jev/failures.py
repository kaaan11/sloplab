"""Typed failure codes for the Jev typed evaluator (A-004).

A Jev operational failure is never a triage decision: the evaluator raises
:class:`JevEvaluationFailure` and assigns no default decision, confidence, or
dimension. The class subclasses the shared :class:`EvaluationFailure`, so the
harness and study runners isolate it as a ``failed`` outcome exactly like an
``llm-json`` failure; ``code`` carries the finer Jev-specific failure code.

Codes (stable, ledger-safe strings; never raw responses, URLs, or keys), with
the shared ``error_kind`` each maps to:

- ``transport.timeout`` (timeout): socket/read timeout, HTTP 408/504.
- ``transport.http_permanent`` (transport): HTTP 401/422 and every other
  non-retried HTTP status (3xx, other 4xx, 5xx except 529).
- ``transport.rate_limited`` (rate-limit): HTTP 429/529 once the retry
  allowance is spent, or when ``Retry-After`` exceeds the wait cap.
- ``transport.error`` (transport): no HTTP status (DNS, refused, TLS). Added
  beyond the A-004 list; not retried.
- ``budget.exceeded`` (budget): the physical dispatch cap refused a send.
- ``response.malformed`` (parse): body is not a JSON object. Added beyond the
  A-004 list.
- ``response.missing_answer`` (parse): a requested question has no typed answer.
- ``response.unknown_option`` (parse): a choice or probability key outside the
  label map.
- ``response.bad_distribution`` (parse): probabilities invalid or not summing to
  1 +/- 1e-6, or a score outside its level range.
- ``response.missing_version`` (parse): the response carries no ``model`` version.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sloplab.evaluators.llm.failures import EvaluationFailure

TRANSPORT_TIMEOUT = "transport.timeout"
TRANSPORT_HTTP_PERMANENT = "transport.http_permanent"
TRANSPORT_RATE_LIMITED = "transport.rate_limited"
TRANSPORT_ERROR = "transport.error"
BUDGET_EXCEEDED = "budget.exceeded"
RESPONSE_MALFORMED = "response.malformed"
RESPONSE_MISSING_ANSWER = "response.missing_answer"
RESPONSE_UNKNOWN_OPTION = "response.unknown_option"
RESPONSE_BAD_DISTRIBUTION = "response.bad_distribution"
RESPONSE_MISSING_VERSION = "response.missing_version"

#: Jev failure code -> shared ``EvaluationFailure.error_kind``.
FAILURE_KINDS: dict[str, str] = {
    TRANSPORT_TIMEOUT: "timeout",
    TRANSPORT_HTTP_PERMANENT: "transport",
    TRANSPORT_RATE_LIMITED: "rate-limit",
    TRANSPORT_ERROR: "transport",
    BUDGET_EXCEEDED: "budget",
    RESPONSE_MALFORMED: "parse",
    RESPONSE_MISSING_ANSWER: "parse",
    RESPONSE_UNKNOWN_OPTION: "parse",
    RESPONSE_BAD_DISTRIBUTION: "parse",
    RESPONSE_MISSING_VERSION: "parse",
}

FAILURE_CODES: tuple[str, ...] = tuple(FAILURE_KINDS)


class JevConfigError(Exception):
    """Raised for configuration problems at construction time (never at dispatch)."""


class BudgetExceeded(Exception):
    """Raised by the counting transport *before* a dispatch the hard cap forbids."""


class JevTransportError(Exception):
    """A dispatch that started but produced no usable HTTP 2xx body.

    ``code`` is one of the ``transport.*`` codes; ``status`` is the HTTP status
    when one was received. The message is a controlled string only.
    """

    def __init__(self, code: str, *, status: int | None = None) -> None:
        self.code = code
        self.status = status
        suffix = f" (HTTP {status})" if status is not None else ""
        super().__init__(f"{code}{suffix}")


class JevTimeout(JevTransportError):
    """Retriable: the request timed out."""

    def __init__(self, *, status: int | None = None) -> None:
        super().__init__(TRANSPORT_TIMEOUT, status=status)


class JevRateLimited(JevTransportError):
    """Retriable: HTTP 429/529. ``retry_after_s`` is the parsed ``Retry-After``."""

    def __init__(self, *, status: int, retry_after_s: float | None) -> None:
        super().__init__(TRANSPORT_RATE_LIMITED, status=status)
        self.retry_after_s = retry_after_s


class JevHttpPermanent(JevTransportError):
    """Terminal: HTTP 401/422 (and other non-retried statuses); never retried."""

    def __init__(self, *, status: int) -> None:
        super().__init__(TRANSPORT_HTTP_PERMANENT, status=status)


class JevResponseError(Exception):
    """A 2xx body that cannot be resolved into the SlopLab contract."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class JevEvaluationFailure(EvaluationFailure):
    """Typed Jev failure record; carries no decision, confidence, or dimensions.

    ``rendered_prompt_hash`` holds the full request-body SHA-256 (the Jev
    request *is* the rendered input). ``adapter_attempts`` counts logical
    attempts of this evaluation; physical dispatches stay with the counting
    transport.
    """

    code: str
    http_status: int | None = None

    def to_record(self) -> dict[str, Any]:
        """Ledger-safe failure record (JSON-serializable)."""
        return {
            "failed": True,
            "code": self.code,
            "error_kind": self.error_kind,
            "adapter_attempts": self.adapter_attempts,
            "request_sha256": self.rendered_prompt_hash,
            "http_status": self.http_status,
        }


def jev_failure(
    code: str,
    *,
    attempts: int,
    request_sha256: str,
    http_status: int | None = None,
) -> JevEvaluationFailure:
    """Build a :class:`JevEvaluationFailure` for a known ``code``."""
    if code not in FAILURE_KINDS:
        raise ValueError(f"unknown Jev failure code {code!r}")
    return JevEvaluationFailure(
        error_kind=FAILURE_KINDS[code],
        adapter_attempts=attempts,
        rendered_prompt_hash=request_sha256,
        detail=code,
        code=code,
        http_status=http_status,
    )
