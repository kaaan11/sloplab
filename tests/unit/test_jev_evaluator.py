"""Mock-based tests for the Jev typed evaluator (A-004). No network access occurs.

The autouse socket guard makes any socket creation, connect, or DNS lookup
raise, so a test that tried to reach the network would fail loudly.
"""

from __future__ import annotations

import hashlib
import io
import json
import socket
import urllib.error
import urllib.request
from email.message import Message
from typing import Any

import pytest

import sloplab.evaluators.jev.transport as transport_module
from sloplab.evaluators.base import list_evaluators
from sloplab.evaluators.jev import (
    CONFIDENCE_SEMANTICS,
    DEFAULT_API_KEY_ENV,
    FAILURE_CODES,
    CountingTransport,
    HttpJevTransport,
    JevConfigError,
    JevEvaluationFailure,
    JevEvaluator,
    JevResponse,
    LabelMap,
)
from sloplab.evaluators.jev.failures import (
    BUDGET_EXCEEDED,
    RESPONSE_BAD_DISTRIBUTION,
    RESPONSE_MALFORMED,
    RESPONSE_MISSING_ANSWER,
    RESPONSE_MISSING_VERSION,
    RESPONSE_UNKNOWN_OPTION,
    TRANSPORT_ERROR,
    TRANSPORT_HTTP_PERMANENT,
    TRANSPORT_RATE_LIMITED,
    TRANSPORT_TIMEOUT,
    JevHttpPermanent,
    JevRateLimited,
    JevTimeout,
    JevTransportError,
)
from sloplab.evaluators.jev.mapping import TRIAGE_V1, build_request, encode_request
from sloplab.evaluators.llm.failures import EvaluationFailure
from sloplab.models.enums import DIMENSIONS, Decision
from sloplab.models.evaluation import EvaluationContext
from sloplab.scoring.harness import SuiteCase, run_case_outcome
from tests._jev_fakes import (
    CASE_ID,
    REPORT_TEXT,
    NetworkBlocked,
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


def make_evaluator(
    inner: ScriptedTransport,
    *,
    cap: int = 10,
    label_map: LabelMap | None = None,
    max_retries: int = 1,
    max_wait_s: float = 60.0,
) -> JevEvaluator:
    _waits, sleep = recording_sleep()
    return JevEvaluator(
        CountingTransport(inner, max_requests=cap),
        model_id=MODEL,
        label_map=label_map,
        max_retries=max_retries,
        max_wait_s=max_wait_s,
        sleep=sleep,
    )


class TestResultSemantics:
    """Acceptance 5: confidence = selected probability; Jev confidence in metadata."""

    def test_confidence_is_selected_class_probability(self) -> None:
        inner = ScriptedTransport(respond(valid_body(jev_confidence=0.4)))
        result = make_evaluator(inner).evaluate(make_report(), make_context())
        assert result.decision is Decision.NEEDS_MANUAL_REVIEW
        assert result.confidence == pytest.approx(0.7)
        assert result.metadata["jev_confidence"] == pytest.approx(0.4)
        assert result.metadata["confidence_semantics"] == CONFIDENCE_SEMANTICS
        assert CONFIDENCE_SEMANTICS == "selected_class_probability"

    def test_selected_probability_follows_the_choice_not_the_maximum(self) -> None:
        body = valid_body(
            selected=Decision.ACCEPT,
            probabilities={
                Decision.ACCEPT: 0.35,
                Decision.REJECT: 0.25,
                Decision.NEEDS_MANUAL_REVIEW: 0.4,
            },
            jev_confidence=0.9,
        )
        result = make_evaluator(ScriptedTransport(respond(body))).evaluate(
            make_report(), make_context()
        )
        assert result.decision is Decision.ACCEPT
        assert result.confidence == pytest.approx(0.35)
        assert result.metadata["jev_confidence"] == pytest.approx(0.9)

    def test_metadata_provenance(self) -> None:
        label_map = LabelMap.random_tokens(4)
        body = valid_body(label_map, model_version="jev-1.13.0")
        inner = ScriptedTransport(respond(body))
        result = make_evaluator(inner, label_map=label_map).evaluate(make_report(), make_context())
        meta = result.metadata
        assert meta["model_version"] == "jev-1.13.0"
        assert meta["model_requested"] == MODEL
        assert meta["label_map_id"] == label_map.id
        assert meta["label_map"] == label_map.as_dict()
        assert meta["criteria_version"] == "triage-v1"
        assert meta["criteria_sha256"] == TRIAGE_V1.sha256
        assert meta["usage"] == {"input_tokens": 812.0, "output_tokens": 40.0, "cost": 0.0000341}
        sent = inner.bodies[0]
        assert meta["request_sha256"] == hashlib.sha256(encode_request(sent)).hexdigest()
        assert meta["response_sha256"] == hashlib.sha256(respond(body).raw).hexdigest()
        assert set(meta["probabilities"]) == {"decision"} | {f"dim_{d}" for d in DIMENSIONS}
        assert meta["probabilities"]["decision"] == {
            "accept": 0.2,
            "reject": 0.1,
            "needs_manual_review": 0.7,
        }
        assert meta["probabilities"]["dim_reproducibility"] == {"0": 0.5, "1": 0.5, "2": 0.0}
        assert meta["request_questions"] == 6
        json.dumps(meta)  # ledger-serializable

    def test_dimensions_are_linear_rescale_of_score(self) -> None:
        result = make_evaluator(ScriptedTransport(respond(valid_body()))).evaluate(
            make_report(), make_context()
        )
        values = result.dimensions.as_dict()
        for index, dimension in enumerate(DIMENSIONS):
            assert values[dimension] == pytest.approx((0.5 + 0.25 * index) / 2)

    def test_no_invented_explanations(self) -> None:
        result = make_evaluator(ScriptedTransport(respond(valid_body()))).evaluate(
            make_report(), make_context()
        )
        assert result.findings == []
        assert result.rationale == ""
        assert result.metadata["capabilities"] == {
            "findings": "unsupported",
            "rationale": "unsupported",
        }

    def test_labels_are_ignored(self) -> None:
        inner = ScriptedTransport(respond(valid_body()), repeat_last=True)
        evaluator = make_evaluator(inner)
        labeled = evaluator.evaluate(make_report(), make_context())
        clean = evaluator.evaluate(
            make_report(), EvaluationContext(report=make_report(), case_id=CASE_ID)
        )
        assert labeled.model_dump() == clean.model_dump()
        assert inner.bodies[0] == inner.bodies[1]
        assert inner.bodies[0]["state"] == REPORT_TEXT


def _drop(path: tuple[str, ...]) -> dict[str, Any]:
    body = valid_body()
    node: Any = body
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]
    return body


def _with(path: tuple[str, ...], value: Any) -> dict[str, Any]:
    body = valid_body()
    node: Any = body
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return body


_RESPONSE_CASES: list[tuple[str, JevResponse]] = [
    (RESPONSE_MALFORMED, JevResponse(raw=b"<html>not json</html>")),
    (RESPONSE_MALFORMED, respond([1, 2, 3])),
    (RESPONSE_MALFORMED, JevResponse(raw=b"\xff\xfe")),
    (RESPONSE_MISSING_VERSION, respond(_drop(("model",)))),
    (RESPONSE_MISSING_VERSION, respond(_with(("model",), ""))),
    (RESPONSE_MISSING_ANSWER, respond(_drop(("answers",)))),
    (RESPONSE_MISSING_ANSWER, respond(_drop(("answers", "decision")))),
    (RESPONSE_MISSING_ANSWER, respond(_drop(("answers", "dim_scope_consistency")))),
    (RESPONSE_MISSING_ANSWER, respond(_with(("answers", "decision", "type"), "score"))),
    (RESPONSE_MISSING_ANSWER, respond(_drop(("answers", "dim_reproducibility", "score")))),
    (RESPONSE_UNKNOWN_OPTION, respond(_with(("answers", "decision", "choice"), "escalate"))),
    (
        RESPONSE_BAD_DISTRIBUTION,
        respond(_with(("answers", "decision", "probabilities", "accept"), 0.1)),
    ),
    (
        RESPONSE_BAD_DISTRIBUTION,
        respond(_with(("answers", "dim_impact_calibration", "probabilities"), {"0": 1.0})),
    ),
    (RESPONSE_BAD_DISTRIBUTION, respond(_with(("answers", "dim_reproducibility", "score"), 2.5))),
    (RESPONSE_BAD_DISTRIBUTION, respond(_with(("answers", "decision", "confidence"), 1.5))),
]

_TRANSPORT_CASES: list[tuple[str, BaseException]] = [
    (TRANSPORT_TIMEOUT, JevTimeout()),
    (TRANSPORT_HTTP_PERMANENT, JevHttpPermanent(status=401)),
    (TRANSPORT_HTTP_PERMANENT, JevHttpPermanent(status=422)),
    (TRANSPORT_RATE_LIMITED, JevRateLimited(status=429, retry_after_s=0.0)),
    (TRANSPORT_RATE_LIMITED, JevRateLimited(status=529, retry_after_s=None)),
    (TRANSPORT_ERROR, JevTransportError(TRANSPORT_ERROR)),
]


class TestFailureRecords:
    """Acceptance 6: every failure code -> typed failure record, no decision."""

    @staticmethod
    def _assert_no_decision(failure: JevEvaluationFailure, code: str) -> None:
        assert failure.code == code
        assert failure.detail == code
        assert isinstance(failure, EvaluationFailure)
        record = failure.to_record()
        assert record["failed"] is True and record["code"] == code
        assert not {"decision", "confidence", "dimensions"} & set(record)
        assert not hasattr(failure, "decision")

    @pytest.mark.parametrize(("code", "response"), _RESPONSE_CASES)
    def test_response_failures(self, code: str, response: JevResponse) -> None:
        inner = ScriptedTransport(response)
        with pytest.raises(JevEvaluationFailure) as info:
            make_evaluator(inner).evaluate(make_report(), make_context())
        self._assert_no_decision(info.value, code)
        assert info.value.error_kind == "parse"
        assert inner.calls == 1  # response failures are never retried

    @pytest.mark.parametrize(("code", "error"), _TRANSPORT_CASES)
    def test_transport_failures(self, code: str, error: BaseException) -> None:
        inner = ScriptedTransport(error, repeat_last=True)
        with pytest.raises(JevEvaluationFailure) as info:
            make_evaluator(inner, max_retries=1, max_wait_s=10.0).evaluate(
                make_report(), make_context()
            )
        self._assert_no_decision(info.value, code)

    def test_budget_failure(self) -> None:
        inner = ScriptedTransport(respond(valid_body()))
        with pytest.raises(JevEvaluationFailure) as info:
            make_evaluator(inner, cap=0).evaluate(make_report(), make_context())
        self._assert_no_decision(info.value, BUDGET_EXCEEDED)
        assert info.value.error_kind == "budget"
        assert inner.calls == 0

    def test_permanent_statuses_are_not_retried(self) -> None:
        for status in (401, 422):
            inner = ScriptedTransport(JevHttpPermanent(status=status), repeat_last=True)
            with pytest.raises(JevEvaluationFailure) as info:
                make_evaluator(inner, max_retries=3).evaluate(make_report(), make_context())
            assert info.value.http_status == status
            assert info.value.adapter_attempts == 1
            assert inner.calls == 1

    def test_every_code_is_exercised(self) -> None:
        exercised = {c for c, _ in _RESPONSE_CASES} | {c for c, _ in _TRANSPORT_CASES}
        exercised.add(BUDGET_EXCEEDED)
        assert exercised == set(FAILURE_CODES)

    def test_harness_isolates_failure_as_outcome(self) -> None:
        case = SuiteCase(
            case_id=CASE_ID,
            kind="canonical",
            parent_id=None,
            operator=None,
            report_class="valid",
            expected_decision="accept",
            expected_dimensions={},
            seed=None,
            fixture_dir=None,
            report=make_report(),
        )
        evaluator = make_evaluator(ScriptedTransport(respond(_drop(("model",)))))
        outcome = run_case_outcome(evaluator, case)
        assert outcome.status == "failed"
        assert outcome.record is None
        assert isinstance(outcome.failure, JevEvaluationFailure)
        assert outcome.failure.code == RESPONSE_MISSING_VERSION


class TestConstruction:
    """Acceptance 8: https only; the API key comes only from the environment."""

    @pytest.mark.parametrize(
        "base_url",
        [
            "http://openrouter.ai/api",
            "http://api.typesafe.ai",
            "ftp://api.typesafe.ai",
            "api.typesafe.ai",
            "https://",
            "https://user:secret@api.typesafe.ai",
            "https://api.typesafe.ai?key=x",
        ],
    )
    def test_non_https_or_unsafe_base_url_rejected(
        self, base_url: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(DEFAULT_API_KEY_ENV, "sk-test")
        with pytest.raises(JevConfigError):
            HttpJevTransport(base_url)

    def test_missing_key_is_a_construction_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(DEFAULT_API_KEY_ENV, raising=False)
        with pytest.raises(JevConfigError, match=DEFAULT_API_KEY_ENV):
            HttpJevTransport.openrouter()
        monkeypatch.setenv(DEFAULT_API_KEY_ENV, "   ")
        with pytest.raises(JevConfigError):
            HttpJevTransport.typesafe_native()

    def test_custom_env_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(DEFAULT_API_KEY_ENV, raising=False)
        monkeypatch.setenv("MY_JEV_KEY", "sk-test")
        transport = HttpJevTransport.openrouter(api_key_env="MY_JEV_KEY")
        assert transport.api_key_env == "MY_JEV_KEY"

    def test_targets_and_repr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(DEFAULT_API_KEY_ENV, "sk-secret-value")
        openrouter = HttpJevTransport.openrouter()
        native = HttpJevTransport.typesafe_native()
        assert openrouter.endpoint == "https://openrouter.ai/api/v1/systemone"
        assert native.endpoint == "https://api.typesafe.ai/v1/systemone"
        assert HttpJevTransport("https://api.typesafe.ai/").endpoint == native.endpoint
        assert "sk-secret-value" not in repr(openrouter)

    def test_bad_timeout_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(DEFAULT_API_KEY_ENV, "sk-test")
        for timeout in (0.0, -1.0, float("inf")):
            with pytest.raises(JevConfigError):
                HttpJevTransport.openrouter(timeout_s=timeout)

    def test_evaluator_requires_counting_transport(self) -> None:
        with pytest.raises(JevConfigError, match="CountingTransport"):
            JevEvaluator(ScriptedTransport())  # type: ignore[arg-type]

    def test_evaluator_rejects_floating_model(self) -> None:
        counting = CountingTransport(ScriptedTransport(), max_requests=1)
        with pytest.raises(JevConfigError):
            JevEvaluator(counting, model_id="~typesafe/jev-latest")

    def test_not_in_default_registry(self) -> None:
        assert "jev-typed" not in list_evaluators()
        assert JevEvaluator.name == "jev-typed"
        assert JevEvaluator.requires_labels is False


def _http_error(status: int, headers: dict[str, str] | None = None) -> urllib.error.HTTPError:
    message = Message()
    for key, value in (headers or {}).items():
        message[key] = value
    return urllib.error.HTTPError(
        "https://openrouter.ai/api/v1/systemone", status, "err", message, io.BytesIO(b"secret")
    )


class TestHttpTransportOffline:
    """HTTP layer behavior with the single exchange function replaced (no sockets)."""

    @pytest.fixture
    def transport(self, monkeypatch: pytest.MonkeyPatch) -> HttpJevTransport:
        monkeypatch.setenv(DEFAULT_API_KEY_ENV, "sk-test")
        return HttpJevTransport.openrouter(timeout_s=7.5)

    def test_success_sends_exact_bytes(
        self, transport: HttpJevTransport, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[tuple[urllib.request.Request, float]] = []
        raw = respond(valid_body()).raw

        def fake_open(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
            seen.append((request, timeout))
            return 200, raw

        monkeypatch.setattr(transport_module, "_open", fake_open)
        body = build_request(REPORT_TEXT, model_id=MODEL, label_map=LabelMap.identity())
        response = transport.decide(body)
        assert response.raw == raw and response.status == 200
        request, timeout = seen[0]
        assert timeout == 7.5
        assert request.full_url == "https://openrouter.ai/api/v1/systemone"
        assert request.get_method() == "POST"
        assert request.data == encode_request(body)
        assert request.get_header("Authorization") == "Bearer sk-test"
        assert request.get_header("Content-type") == "application/json"

    @pytest.mark.parametrize(
        ("error", "expected_type", "status"),
        [
            (_http_error(401), JevHttpPermanent, 401),
            (_http_error(422), JevHttpPermanent, 422),
            (_http_error(500), JevHttpPermanent, 500),
            (_http_error(302, {"Location": "http://evil.example"}), JevHttpPermanent, 302),
            (_http_error(408), JevTimeout, 408),
            (_http_error(429, {"Retry-After": "3"}), JevRateLimited, 429),
            (_http_error(529), JevRateLimited, 529),
            (TimeoutError("slow"), JevTimeout, None),
            (urllib.error.URLError(TimeoutError("slow")), JevTimeout, None),
            (urllib.error.URLError("refused"), JevTransportError, None),
            (ConnectionResetError("reset"), JevTransportError, None),
        ],
    )
    def test_error_classification(
        self,
        transport: HttpJevTransport,
        monkeypatch: pytest.MonkeyPatch,
        error: BaseException,
        expected_type: type[JevTransportError],
        status: int | None,
    ) -> None:
        def fake_open(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
            raise error

        monkeypatch.setattr(transport_module, "_open", fake_open)
        with pytest.raises(expected_type) as info:
            transport.decide({"model": MODEL})
        assert info.value.status == status
        assert "secret" not in str(info.value)
        assert info.value.__cause__ is None

    def test_retry_after_parsed(
        self, transport: HttpJevTransport, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_open(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
            raise _http_error(429, {"Retry-After": "2.5"})

        monkeypatch.setattr(transport_module, "_open", fake_open)
        with pytest.raises(JevRateLimited) as info:
            transport.decide({"model": MODEL})
        assert info.value.retry_after_s == 2.5

    @pytest.mark.parametrize("value", ["inf", "nan", "soon", "-4"])
    def test_unusable_retry_after(self, value: str) -> None:
        message = Message()
        message["Retry-After"] = value
        parsed = transport_module.parse_retry_after(message)
        assert parsed is None or parsed == 0.0


class TestNoSockets:
    """Acceptance 9: the guard is active and would catch a real dispatch."""

    def test_guard_blocks_socket_creation(self) -> None:
        with pytest.raises(NetworkBlocked):
            socket.socket()
        with pytest.raises(NetworkBlocked):
            socket.getaddrinfo("api.typesafe.ai", 443)

    def test_real_exchange_path_hits_the_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The genuine urllib path must stop at the guard (connect/DNS), proving
        # that no test in this module could reach the network silently.
        monkeypatch.setenv(DEFAULT_API_KEY_ENV, "sk-test")
        transport = HttpJevTransport.openrouter(timeout_s=1.0)
        with pytest.raises(NetworkBlocked):
            transport.decide({"model": MODEL})

    def test_full_evaluation_uses_no_socket(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(DEFAULT_API_KEY_ENV, "sk-test")
        raw = respond(valid_body()).raw
        monkeypatch.setattr(transport_module, "_open", lambda request, timeout: (200, raw))
        evaluator = JevEvaluator(
            CountingTransport(HttpJevTransport.openrouter(), max_requests=1), model_id=MODEL
        )
        result = evaluator.evaluate(make_report(), make_context())
        assert result.decision is Decision.NEEDS_MANUAL_REVIEW
