"""Robustness tests for LLM Evaluator JSON response parsing, chatter stripping, and recovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sloplab.evaluators.llm.adapter import LlmEvaluator, LLMResponse
from sloplab.models.enums import Decision, Severity
from sloplab.models.evaluation import EvaluationContext
from sloplab.models.report import ReportDocument

REPO_ROOT = Path(__file__).resolve().parents[2]


class MockClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.call_idx = 0

    def complete(self, prompt: str) -> LLMResponse:
        resp = self.responses[min(self.call_idx, len(self.responses) - 1)]
        self.call_idx += 1
        return LLMResponse(text=resp, latency_ms=10)


@pytest.fixture
def sample_doc() -> ReportDocument:
    return ReportDocument(
        fixture_id="doc-001",
        path="doc.md",
        raw_text="Sample vulnerability report content.",
        title="Sample",
        sections=(),
    )


def test_llm_evaluator_fenced_markdown_json(sample_doc: ReportDocument) -> None:
    payload = {
        "decision": "accept",
        "confidence": 0.88,
        "dimensions": {
            "reproducibility": 0.9,
            "evidence_completeness": 0.9,
            "claim_evidence_consistency": 0.9,
            "impact_calibration": 0.9,
            "scope_consistency": 0.9,
        },
        "findings": [{"code": "VALID_AUTHZ", "severity": "CRITICAL", "evidence": "Confirmed"}],
        "rationale": "Markdown fenced output.",
    }
    fenced_text = f"```json\n{json.dumps(payload, indent=2)}\n```"

    evaluator = LlmEvaluator(MockClient([fenced_text]), enabled=True)
    ctx = EvaluationContext(report=sample_doc, case_id="case-fence", labels={})

    result = evaluator.evaluate(sample_doc, ctx)
    assert result.decision == Decision.ACCEPT
    assert result.confidence == pytest.approx(0.88)
    assert len(result.findings) == 1
    assert result.findings[0].severity == Severity.CRITICAL


def test_llm_evaluator_conversational_chatter(sample_doc: ReportDocument) -> None:
    payload = {
        "decision": "reject",
        "confidence": 0.75,
        "dimensions": {
            "reproducibility": 0.3,
            "evidence_completeness": 0.4,
            "claim_evidence_consistency": 0.5,
            "impact_calibration": 0.5,
            "scope_consistency": 0.5,
        },
        "findings": [{"code": "NO_VULN", "severity": "low", "evidence": "None"}],
        "rationale": "Rejection rationale.",
    }
    chatter_text = (
        "Hello! I analyzed the security report thoroughly.\n"
        f"Here is the evaluation JSON object:\n{json.dumps(payload)}\n"
        "Let me know if you need any further assistance with triage!"
    )

    evaluator = LlmEvaluator(MockClient([chatter_text]), enabled=True)
    ctx = EvaluationContext(report=sample_doc, case_id="case-chatter", labels={})

    result = evaluator.evaluate(sample_doc, ctx)
    assert result.decision == Decision.REJECT
    assert result.confidence == pytest.approx(0.75)


def test_llm_evaluator_unparseable_output_retry_and_fallback(sample_doc: ReportDocument) -> None:
    garbage_responses = [
        "I cannot evaluate this vulnerability report.",
        "Error 500: Model overwhelmed.",
        "Not a JSON response.",
    ]
    client = MockClient(garbage_responses)
    evaluator = LlmEvaluator(client, max_retries=2, enabled=True)
    ctx = EvaluationContext(report=sample_doc, case_id="case-garbage", labels={})

    result = evaluator.evaluate(sample_doc, ctx)
    assert client.call_idx == 3  # 1 initial + 2 retries
    assert result.decision == Decision.NEEDS_MANUAL_REVIEW
    assert result.confidence == 0.0
    assert result.metadata.get("failed") is True
