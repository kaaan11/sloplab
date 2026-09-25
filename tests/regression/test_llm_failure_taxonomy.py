"""A-008: strict llm-json output contract and failure taxonomy. No live calls."""

from __future__ import annotations

import io
import json
import urllib.error
from email.message import Message
from typing import Any

import pytest

from sloplab.corpus.parser import parse_report
from sloplab.evaluators.llm.adapter import (
    REFUSAL_MAX_CHARS,
    HttpLLMClient,
    LlmEvaluator,
    LLMResponse,
)
from sloplab.evaluators.llm.failures import (
    ERROR_KINDS,
    FAILURE_CLASSES,
    PARSE_SCHEMA_DETAILS,
    PARSE_SYNTAX_DETAILS,
    REFUSAL_DETAILS,
    EvaluationFailure,
    classify_dispatch_error,
    failure_class,
)
from sloplab.experiments.pilot import CountingClient
from sloplab.models.enums import Decision
from sloplab.models.evaluation import EvaluationContext

PAYLOAD: dict[str, Any] = {
    "decision": "reject",
    "confidence": 0.7,
    "dimensions": {
        "reproducibility": 0.2,
        "evidence_completeness": 0.3,
        "claim_evidence_consistency": 0.4,
        "impact_calibration": 0.5,
        "scope_consistency": 0.6,
    },
    "findings": [],
    "rationale": "No boundary crossed.",
}


def _text(**overrides: Any) -> str:
    payload = dict(PAYLOAD)
    payload.update(overrides)
    return json.dumps(payload)


class _Static:
    def __init__(self, text: str, *, provider_refusal: bool = False) -> None:
        self.text = text
        self.provider_refusal = provider_refusal
        self.calls = 0

    def complete(self, prompt: str) -> LLMResponse:
        _ = prompt
        self.calls += 1
        return LLMResponse(text=self.text, latency_ms=1, provider_refusal=self.provider_refusal)


class _Raising:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc
        self.calls = 0

    def complete(self, prompt: str) -> LLMResponse:
        _ = prompt
        self.calls += 1
        raise self.exc


class _CodedError(Exception):
    def __init__(self, code: object) -> None:
        super().__init__(f"status {code!r} secret-canary")
        self.code = code


def _evaluate(client: Any, max_retries: int = 2) -> Any:
    doc = parse_report("# T\n\n## Summary\n\nBody.\n", fixture_id="x", path="x")
    evaluator = LlmEvaluator(client=client, max_retries=max_retries, enabled=True)
    return evaluator.evaluate(doc, EvaluationContext(report=doc, case_id="x", labels={}))


def _failure(text: str) -> EvaluationFailure:
    client = _Static(text)
    with pytest.raises(EvaluationFailure) as exc_info:
        _evaluate(client)
    assert client.calls == 1, "response-content failures are terminal"
    assert exc_info.value.adapter_attempts == 1
    return exc_info.value


# --- strict output contract -------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        _text(),
        f"  \n{_text()}\n\n",
        f"```json\n{_text()}\n```",
        f"```JSON\n{_text()}\n```\n",
        f"```\n{_text()}\n```",
        json.dumps({k: v for k, v in PAYLOAD.items() if k not in ("findings", "rationale")}),
    ],
)
def test_strict_contract_accepts_exact_object(text: str) -> None:
    result = _evaluate(_Static(text))
    assert result.decision == Decision.REJECT
    assert result.metadata["adapter"] == "strict-json"


@pytest.mark.parametrize(
    ("text", "detail"),
    [
        ("", "parse.empty_response"),
        ("   \n\t", "parse.empty_response"),
        ("The report looks plausible.", "parse.no_json_object"),
        ("I cannot reproduce the issue from the given steps.", "parse.no_json_object"),
        ("{not json", "parse.invalid_json"),
        ('{"decision": "reject", "confidence": NaN}', "parse.invalid_json"),
        (f"Here you go:\n{_text()}", "parse.extra_text"),
        (f"{_text()}\nLet me know if you need more.", "parse.extra_text"),
        (f"{_text()}\n{_text()}", "parse.extra_text"),
        (f"Result:\n```json\n{_text()}\n```", "parse.extra_text"),
        (f"```json\n{_text()}\n```\n```json\n{_text()}\n```", "parse.extra_text"),
    ],
)
def test_syntax_failures_have_distinct_codes(text: str, detail: str) -> None:
    failure = _failure(text)
    assert failure.error_kind == "parse"
    assert failure.detail == detail
    assert failure_class(failure.error_kind, failure.detail) == "json_syntax"


@pytest.mark.parametrize(
    ("text", "detail"),
    [
        (json.dumps([1, 2, 3]), "parse.non_object"),
        (json.dumps("accept"), "parse.non_object"),
        (_text(verdict="accept"), "parse.unknown_keys"),
        (_text(decision="maybe"), "parse.invalid_decision"),
        (_text(confidence=True), "parse.invalid_confidence"),
        (_text(confidence="0.7"), "parse.invalid_confidence"),
        (_text(dimensions={**PAYLOAD["dimensions"], "novelty": 0.5}), "parse.invalid_dimensions"),
        (
            _text(dimensions={**PAYLOAD["dimensions"], "reproducibility": "0.2"}),
            "parse.invalid_dimensions",
        ),
        (
            _text(dimensions={**PAYLOAD["dimensions"], "reproducibility": True}),
            "parse.invalid_dimensions",
        ),
        (
            _text(dimensions={**PAYLOAD["dimensions"], "reproducibility": 1.5}),
            "parse.invalid_dimensions",
        ),
        (_text(findings={"code": "X"}), "parse.invalid_findings"),
        (_text(rationale=["a", "b"]), "parse.invalid_rationale"),
    ],
)
def test_schema_failures_have_distinct_codes(text: str, detail: str) -> None:
    failure = _failure(text)
    assert failure.error_kind == "parse"
    assert failure.detail == detail
    assert failure_class(failure.error_kind, failure.detail) == "schema"


# --- refusal ------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "I cannot help with that.",
        "I can't assist with this request.",
        "I’m sorry, but I can’t help with that.",
        "Sorry, I won't evaluate this report.",
        "I apologize, but I am unable to comply.",
        "I'm unable to provide an assessment.",
        "I must decline.",
    ],
)
def test_conservative_refusal_patterns(text: str) -> None:
    failure = _failure(text)
    assert failure.error_kind == "refusal"
    assert failure.detail == "refusal.text_pattern"
    assert text not in str(failure)
    assert failure_class(failure.error_kind, failure.detail) == "refusal"


@pytest.mark.parametrize(
    "text",
    [
        # Pattern not at the start of the response.
        "The report is thin. I cannot help noticing the missing steps.",
        # Contains a brace: treated as a (broken) JSON attempt, never a refusal.
        "I cannot help with that. {",
        # Too long for the conservative rule.
        "I cannot help with that. " + "x" * REFUSAL_MAX_CHARS,
    ],
)
def test_near_refusals_stay_parse_failures(text: str) -> None:
    failure = _failure(text)
    assert failure.error_kind == "parse"


def test_needs_manual_review_is_a_decision_not_a_refusal() -> None:
    result = _evaluate(_Static(_text(decision="needs_manual_review")))
    assert result.decision == Decision.NEEDS_MANUAL_REVIEW


def test_provider_refusal_flag_wins_and_is_terminal() -> None:
    client = _Static(_text(), provider_refusal=True)
    with pytest.raises(EvaluationFailure) as exc_info:
        _evaluate(client)
    assert (exc_info.value.error_kind, exc_info.value.detail) == ("refusal", "refusal.provider")
    assert client.calls == 1


class _FakeHttpResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _http_client(monkeypatch: pytest.MonkeyPatch, message: dict[str, Any]) -> HttpLLMClient:
    import urllib.request

    body = json.dumps({"choices": [{"message": message}]}).encode()
    monkeypatch.setenv("A008_KEY", "k")
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda request, timeout=None: _FakeHttpResponse(body)
    )
    return HttpLLMClient(model="m", api_key_env="A008_KEY", endpoint="https://example.invalid/v1")


def test_http_client_surfaces_provider_refusal_without_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _http_client(monkeypatch, {"content": None, "refusal": "REFUSAL-CANARY"})
    response = client.complete("p")
    assert response.provider_refusal is True
    assert "REFUSAL-CANARY" not in response.text
    with pytest.raises(EvaluationFailure) as exc_info:
        _evaluate(client, max_retries=0)
    assert exc_info.value.error_kind == "refusal"
    assert "REFUSAL-CANARY" not in str(exc_info.value)


def test_http_client_null_content_is_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _http_client(monkeypatch, {"content": None})
    response = client.complete("p")
    assert (response.text, response.provider_refusal) == ("", False)
    with pytest.raises(EvaluationFailure) as exc_info:
        _evaluate(client, max_retries=3)
    # Previously a None content crashed the parser and was retried as transport.
    assert (exc_info.value.error_kind, exc_info.value.detail) == ("parse", "parse.empty_response")
    assert exc_info.value.adapter_attempts == 1


# --- permanent vs transient HTTP ----------------------------------------------


@pytest.mark.parametrize("status", [400, 401, 403, 404, 413, 422])
def test_permanent_http_is_terminal(status: int) -> None:
    kind, detail, retriable = classify_dispatch_error(_CodedError(status))
    assert (kind, detail, retriable) == ("http-permanent", f"http.{status}", False)
    transport = _Raising(_CodedError(status))
    counting = CountingClient(transport, max_requests=10)
    with pytest.raises(EvaluationFailure) as exc_info:
        _evaluate(counting, max_retries=3)
    assert transport.calls == 1
    assert exc_info.value.adapter_attempts == 1
    assert exc_info.value.detail == f"http.{status}"
    assert "secret-canary" not in str(exc_info.value)
    # The request really went out: it stays a counted physical dispatch.
    assert counting.physical_dispatches == 1
    assert counting.errors == 1
    assert failure_class(exc_info.value.error_kind, exc_info.value.detail) == "http_permanent"


def test_real_urllib_http_error_is_classified() -> None:
    exc = urllib.error.HTTPError(
        "https://example.invalid", 401, "Unauthorized", Message(), io.BytesIO(b"")
    )
    assert classify_dispatch_error(exc) == ("http-permanent", "http.401", False)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (408, ("transport", "transport.error", True)),
        (429, ("rate-limit", "rate_limited", True)),
        (500, ("transport", "transport.error", True)),
        (503, ("transport", "transport.error", True)),
        ("401", ("transport", "transport.error", True)),
        (True, ("transport", "transport.error", True)),
    ],
)
def test_transient_or_non_http_codes_stay_retriable(code: object, expected: object) -> None:
    assert classify_dispatch_error(_CodedError(code)) == expected


def test_transient_5xx_is_retried() -> None:
    transport = _Raising(_CodedError(503))
    with pytest.raises(EvaluationFailure) as exc_info:
        _evaluate(transport, max_retries=2)
    assert transport.calls == 3
    assert exc_info.value.error_kind == "transport"


# --- taxonomy bookkeeping -----------------------------------------------------


def test_existing_error_kinds_are_stable_and_new_ones_appended() -> None:
    legacy = ("parse", "timeout", "transport", "budget", "legacy", "rate-limit", "deadline")
    assert ERROR_KINDS[: len(legacy)] == legacy
    assert set(ERROR_KINDS[len(legacy) :]) == {"refusal", "http-permanent"}


def test_failure_class_is_total_and_conservative() -> None:
    assert not PARSE_SYNTAX_DETAILS & PARSE_SCHEMA_DETAILS
    for kind in ERROR_KINDS:
        if kind == "parse":
            continue
        assert failure_class(kind, "whatever") in FAILURE_CLASSES
        assert failure_class(kind, "whatever") != "unknown"
    for detail in REFUSAL_DETAILS:
        assert failure_class("refusal", detail) == "refusal"
    assert failure_class("parse", "parse.something_new") == "unknown"
    assert failure_class("mystery", "x") == "unknown"
