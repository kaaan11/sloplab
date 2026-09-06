"""Mock-based tests for the optional LLM adapter. No network access occurs."""

from __future__ import annotations

import json
from typing import Any

import pytest

from sloplab.corpus.parser import parse_report
from sloplab.evaluators.llm.adapter import (
    AdapterError,
    FlakyThenSuccessClient,
    LlmEvaluator,
)
from sloplab.models.enums import Decision
from sloplab.models.evaluation import EvaluationContext


def make_report() -> Any:
    return parse_report(
        "# T\n\n## Summary\n\nA complete report body for adapter testing.\n",
        fixture_id="canonical-llm-001",
        path="x",
    )


def make_context() -> EvaluationContext:
    report = make_report()
    return EvaluationContext(
        report=report,
        case_id="canonical-llm-001",
        labels={"expected_decision": "reject"},  # must be ignored by the adapter
    )


VALID_PAYLOAD: dict[str, Any] = {
    "decision": "needs_manual_review",
    "confidence": 0.62,
    "dimensions": {
        "reproducibility": 0.7,
        "evidence_completeness": 0.6,
        "claim_evidence_consistency": 0.65,
        "impact_calibration": 0.55,
        "scope_consistency": 0.6,
    },
    "findings": [{"code": "THIN_EVIDENCE", "severity": "low", "evidence": "impact thin"}],
    "rationale": "Hedged claims with partial evidence.",
}


def payload_text(**overrides: Any) -> str:
    payload = dict(VALID_PAYLOAD)
    payload.update(overrides)
    return json.dumps(payload)


class TestConstructionSafety:
    def test_disabled_by_default(self) -> None:
        with pytest.raises(AdapterError, match="disabled by default"):
            LlmEvaluator(client=FlakyThenSuccessClient(0, payload_text()))

    def test_requires_client_when_enabled(self) -> None:
        with pytest.raises(AdapterError, match="LLMClient"):
            LlmEvaluator(client=None, enabled=True)  # type: ignore[arg-type]


class TestStrictParsing:
    def evaluator_with(self, response_text: str) -> LlmEvaluator:
        return LlmEvaluator(client=FlakyThenSuccessClient(0, response_text), enabled=True)

    def test_valid_payload_round_trips(self) -> None:
        result = self.evaluator_with(payload_text()).evaluate(make_report(), make_context())
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW
        assert result.confidence == pytest.approx(0.62)
        assert result.dimensions.reproducibility == pytest.approx(0.7)
        assert result.findings[0].code == "THIN_EVIDENCE"
        assert result.metadata["failed"] is False

    def test_json_embedded_in_prose_is_extracted(self) -> None:
        text = f"Sure! Here is my assessment:\n{payload_text()}\nHope that helps."
        result = self.evaluator_with(text).evaluate(make_report(), make_context())
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW

    def test_malformed_json_becomes_failed_record(self) -> None:
        result = self.evaluator_with("{not json at all").evaluate(make_report(), make_context())
        assert result.confidence == 0.0
        assert result.metadata["failed"] is True
        assert "invalid JSON" in result.rationale or "no JSON" in result.rationale

    def test_missing_json_becomes_failed_record(self) -> None:
        result = self.evaluator_with("I cannot help with that.").evaluate(
            make_report(), make_context()
        )
        assert result.metadata["failed"] is True

    def test_invalid_decision_value_fails(self) -> None:
        result = self.evaluator_with(payload_text(decision="probably_fine")).evaluate(
            make_report(), make_context()
        )
        assert result.metadata["failed"] is True
        assert "decision" in result.rationale

    def test_out_of_range_confidence_fails(self) -> None:
        result = self.evaluator_with(payload_text(confidence=1.7)).evaluate(
            make_report(), make_context()
        )
        assert result.metadata["failed"] is True

    def test_missing_dimension_fails(self) -> None:
        dims: dict[str, Any] = {
            k: v for k, v in VALID_PAYLOAD["dimensions"].items() if k != "scope_consistency"
        }
        result = self.evaluator_with(payload_text(dimensions=dims)).evaluate(
            make_report(), make_context()
        )
        assert result.metadata["failed"] is True

    def test_non_object_top_level_fails(self) -> None:
        result = self.evaluator_with(json.dumps([1, 2, 3])).evaluate(make_report(), make_context())
        assert result.metadata["failed"] is True

    def test_bad_finding_codes_are_dropped_not_fatal(self) -> None:
        findings = [
            {"code": "lowercase_bad", "severity": "low"},
            {"code": "GOOD_CODE", "severity": "high", "evidence": "x"},
            "not-even-a-dict",
        ]
        result = self.evaluator_with(payload_text(findings=findings)).evaluate(
            make_report(), make_context()
        )
        assert not result.metadata["failed"]
        assert [f.code for f in result.findings] == ["GOOD_CODE"]


class TestRetryAndFailureSemantics:
    def test_transient_transport_error_retries_then_succeeds(self) -> None:
        client = FlakyThenSuccessClient(failures=2, response_text=payload_text())
        evaluator = LlmEvaluator(client=client, max_retries=2, enabled=True)
        result = evaluator.evaluate(make_report(), make_context())
        assert client.calls == 3
        assert not result.metadata.get("failed", False)

    def test_exhausted_retries_yield_failed_record(self) -> None:
        client = FlakyThenSuccessClient(failures=5, response_text=payload_text())
        evaluator = LlmEvaluator(client=client, max_retries=1, enabled=True)
        result = evaluator.evaluate(make_report(), make_context())
        assert result.metadata["failed"] is True
        assert "TimeoutError" in result.rationale

    def test_labels_never_affect_output(self) -> None:
        evaluator = LlmEvaluator(client=FlakyThenSuccessClient(0, payload_text()), enabled=True)
        ctx_labeled = make_context()
        ctx_clean = EvaluationContext(report=make_report(), case_id="canonical-llm-001")
        r1 = evaluator.evaluate(make_report(), ctx_labeled)
        r2 = evaluator.evaluate(make_report(), ctx_clean)
        assert r1.model_dump() == r2.model_dump()


class TestRegistryExclusion:
    def test_llm_adapter_not_in_default_registry(self) -> None:
        from sloplab.evaluators.base import list_evaluators

        assert "llm-json" not in list_evaluators()


class TestHttpLLMClientTimeout:
    """The config-driven timeout reaches the HTTP layer unchanged (P2-2)."""

    class _FakeResponse:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return self._body

    def test_timeout_is_passed_to_urlopen(self, monkeypatch: Any) -> None:
        import urllib.request

        from sloplab.evaluators.llm.adapter import HttpLLMClient, LLMResponse

        captured: dict[str, Any] = {}

        def fake_urlopen(request: Any, timeout: float | None = None) -> Any:
            captured["timeout"] = timeout
            inner = json.dumps(
                {"decision": "accept", "confidence": 0.9, "dimensions": {}, "findings": []}
            )
            body = json.dumps({"choices": [{"message": {"content": inner}}]}).encode()
            return type(self)._FakeResponse(body)

        monkeypatch.setenv("SLOPLAB_LLM_API_KEY", "test-key")
        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        client = HttpLLMClient(
            model="m",
            api_key_env="SLOPLAB_LLM_API_KEY",
            endpoint="https://example.invalid/v1/chat/completions",
            timeout_s=7,
        )
        response = client.complete("hello")
        assert isinstance(response, LLMResponse)
        assert captured["timeout"] == 7

    def test_non_positive_timeout_rejected(self, monkeypatch: Any) -> None:
        from sloplab.evaluators.llm.adapter import HttpLLMClient

        monkeypatch.setenv("SLOPLAB_LLM_API_KEY", "test-key")
        with pytest.raises(AdapterError, match="timeout_s must be positive"):
            HttpLLMClient(
                model="m",
                api_key_env="SLOPLAB_LLM_API_KEY",
                endpoint="https://example.invalid/v1",
                timeout_s=0,
            )
