"""Typed evaluation failures shared by the LLM adapter, harness, and pilot (E2a).

An operational failure (unparseable response, timeout, transport error, spent
budget) is an exception, never a triage decision. :class:`EvaluationFailure`
carries the error kind, the logical adapter attempt count, and the rendered
prompt identity — never a decision, confidence, or dimensions.

``adapter_attempts`` counts logical adapter attempts (1 + retries consumed), not
physical dispatches; the physical budget accounting stays with the pilot's
counting client (centralized in E2b, exact in E2b-r1: the reservation
immediately precedes the transport start, so refused waits consume nothing).
``detail`` is a short controlled description: no raw model responses, full
prompts, credentials, or unchecked exception dumps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sloplab.models.evaluation import EvaluationResult

#: Known error kinds. ``legacy`` marks pre-E2a failed placeholders converted at
#: an outcome boundary; it carries no measured attempt count semantics beyond
#: one observed evaluation call. ``rate-limit`` marks explicit HTTP 429 /
#: provider backpressure (retriable); ``deadline`` marks waits or dispatches
#: refused by the run's monotonic deadline (terminal). ``parse`` covers every
#: response-content failure (JSON syntax, strict format, schema); the ``detail``
#: code tells them apart (:data:`PARSE_SYNTAX_DETAILS`,
#: :data:`PARSE_SCHEMA_DETAILS`). ``refusal`` (A-008) marks an explicit model
#: refusal: a provider-native refusal field, or a JSON-free response matching the
#: adapter's small documented refusal pattern set (terminal). ``http-permanent``
#: (A-008) marks an HTTP 4xx status other than 408/429 (terminal: auth, invalid
#: request, unknown model do not heal on retry). Existing kinds keep their
#: names; new kinds are appended.
ERROR_KINDS = (
    "parse",
    "timeout",
    "transport",
    "budget",
    "legacy",
    "rate-limit",
    "deadline",
    "refusal",
    "http-permanent",
)

#: ``parse`` detail codes meaning the response text is not exactly one valid
#: JSON document. ``parse.extra_text`` is the strict-format code: a JSON object
#: was found but other text surrounds it (prose, a second object, or text
#: outside the optional single code fence).
PARSE_SYNTAX_DETAILS = frozenset(
    {
        "parse.empty_response",
        "parse.no_json_object",
        "parse.invalid_json",
        "parse.extra_text",
    }
)

#: ``parse`` detail codes meaning the JSON document parsed but violates the
#: normalized output schema (wrong top-level type, unknown keys, bad values).
PARSE_SCHEMA_DETAILS = frozenset(
    {
        "parse.non_object",
        "parse.unknown_keys",
        "parse.invalid_decision",
        "parse.invalid_confidence",
        "parse.invalid_dimensions",
        "parse.invalid_findings",
        "parse.invalid_rationale",
    }
)

#: ``refusal`` detail codes. ``refusal.provider``: the provider response carried
#: an explicit refusal field. ``refusal.text_pattern``: the response contained no
#: ``{`` at all and matched the adapter's refusal pattern set. This is a
#: surface-form classification only; it makes no claim about why the model
#: refused, and a valid ``needs_manual_review`` decision is never a refusal.
REFUSAL_DETAILS = frozenset({"refusal.provider", "refusal.text_pattern"})

#: Coarse failure classes returned by :func:`failure_class`.
FAILURE_CLASSES = (
    "json_syntax",
    "schema",
    "refusal",
    "http_permanent",
    "rate_limit",
    "timeout",
    "transport",
    "budget",
    "deadline",
    "legacy",
    "unknown",
)

#: 4xx statuses that stay retriable: 408 Request Timeout and 429 Too Many Requests.
_HTTP_TRANSIENT_4XX = frozenset({408, 429})

_SIMPLE_FAILURE_CLASSES = {
    "refusal": "refusal",
    "http-permanent": "http_permanent",
    "rate-limit": "rate_limit",
    "timeout": "timeout",
    "transport": "transport",
    "budget": "budget",
    "deadline": "deadline",
    "legacy": "legacy",
}


class BudgetExhausted(Exception):
    """Raised when the configured request budget is spent (physical cap)."""


class DeadlineExceeded(Exception):
    """Raised instead of sleeping when a required wait does not fit the deadline,
    or instead of dispatching when the run deadline has already passed."""


def classify_dispatch_error(exc: BaseException) -> tuple[str, str, bool]:
    """Map a dispatch error to ``(error_kind, detail_code, retriable)``.

    Terminal (never retried): spent budget and deadline refusal — retrying
    cannot succeed — and permanent HTTP statuses (an integer ``code`` in
    400-499 other than 408 Request Timeout and 429 Too Many Requests), whose
    detail is ``http.<status>``. Retriable: timeouts, transports (including
    HTTP 5xx and 408), and explicit 429 / provider backpressure. Detail codes
    are stable strings; exception text (which may carry credentials, URLs, or
    raw responses) is never copied.
    """
    if isinstance(exc, BudgetExhausted):
        return ("budget", "budget.exhausted", False)
    if isinstance(exc, DeadlineExceeded):
        return ("deadline", "deadline.exceeded", False)
    code = getattr(exc, "code", None)
    if code == 429:
        return ("rate-limit", "rate_limited", True)
    if (
        isinstance(code, int)
        and not isinstance(code, bool)
        and 400 <= code <= 499
        and code not in _HTTP_TRANSIENT_4XX
    ):
        return ("http-permanent", f"http.{code}", False)
    if isinstance(exc, TimeoutError):
        return ("timeout", "transport.timeout", True)
    return ("transport", "transport.error", True)


def failure_class(error_kind: str, detail: str) -> str:
    """Return the coarse failure class (one of :data:`FAILURE_CLASSES`).

    Derived only from the stable ``(error_kind, detail)`` codes already stored
    in outcome rows, so existing ledgers classify without a schema change.
    ``parse`` splits into ``json_syntax`` and ``schema`` by detail code; an
    unrecognized pair maps to ``unknown`` rather than being guessed.
    """
    if error_kind == "parse":
        if detail in PARSE_SYNTAX_DETAILS:
            return "json_syntax"
        if detail in PARSE_SCHEMA_DETAILS:
            return "schema"
        return "unknown"
    return _SIMPLE_FAILURE_CLASSES.get(error_kind, "unknown")


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
