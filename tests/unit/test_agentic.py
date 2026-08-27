"""Tests for agentic triage evaluator and tool-use metrics (Phase 7)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sloplab.corpus.loader import load_canonical_fixture
from sloplab.evaluators.agentic import (
    AgenticTriageEvaluator,
    AgentStep,
    ToolDefinition,
)
from sloplab.models.enums import Decision
from sloplab.models.evaluation import DimensionScores, EvaluationContext, EvaluationResult
from sloplab.models.run import CaseRecord
from sloplab.scoring.metrics import compute_agentic_metrics


@pytest.fixture(scope="module")
def sample_report() -> Any:
    fixture_dir = Path(__file__).resolve().parents[2] / "corpus/canonical/authz-001"
    return load_canonical_fixture(fixture_dir, fixture_dir.parent.parent).report


class MockReActClient:
    def __init__(self) -> None:
        self.step_idx = 0

    def plan_step(
        self,
        report_text: str,
        history: list[AgentStep],
        available_tools: list[ToolDefinition],
    ) -> tuple[AgentStep, bool]:
        self.step_idx += 1
        if self.step_idx == 1:
            return (
                AgentStep(
                    thought="Need to check if controller exists in repo",
                    tool_name="search_source_tree",
                    tool_args={"query": "DocumentController"},
                ),
                False,
            )
        if self.step_idx == 2:
            return (
                AgentStep(
                    thought="Controller confirmed. Attempting PoC reproduction in sandbox",
                    tool_name="execute_poc_sandbox",
                    tool_args={"command": "curl https://demo.example.org/api/v1/documents/1042"},
                ),
                False,
            )
        return (
            AgentStep(
                thought="PoC returned 200 OK with cross-tenant data. Vulnerability verified.",
                tool_name=None,
            ),
            True,
        )


def test_agentic_evaluator_reproduction_cycle(sample_report: Any) -> None:
    client = MockReActClient()
    evaluator = AgenticTriageEvaluator(client=client, max_steps=5)
    ctx = EvaluationContext(report=sample_report, case_id="case-101", labels={})

    result = evaluator.evaluate(sample_report, ctx)

    assert result.decision == Decision.ACCEPT
    assert result.confidence == pytest.approx(0.90)
    assert result.metadata["tool_calls_count"] == 2
    assert len(result.metadata["agent_trace"]) == 3


def test_agentic_evaluator_respects_max_steps(sample_report: Any) -> None:
    class InfiniteLoopClient:
        def plan_step(
            self,
            report_text: str,
            history: list[AgentStep],
            available_tools: list[ToolDefinition],
        ) -> tuple[AgentStep, bool]:
            return (
                AgentStep(
                    thought="Looping tool call",
                    tool_name="search_source_tree",
                    tool_args={"query": "loop"},
                ),
                False,
            )

    evaluator = AgenticTriageEvaluator(client=InfiniteLoopClient(), max_steps=3)
    ctx = EvaluationContext(report=sample_report, case_id="case-loop", labels={})

    result = evaluator.evaluate(sample_report, ctx)
    assert len(result.metadata["agent_trace"]) == 3
    assert result.metadata["tool_calls_count"] == 3


def test_compute_agentic_metrics() -> None:
    dims = {
        "reproducibility": 0.8,
        "evidence_completeness": 0.8,
        "claim_evidence_consistency": 0.8,
        "impact_calibration": 0.8,
        "scope_consistency": 0.8,
    }
    r1 = EvaluationResult(
        evaluator_name="agentic",
        evaluator_version="1.0",
        case_id="c1",
        decision=Decision.ACCEPT,
        confidence=0.9,
        dimensions=DimensionScores.from_dict(dims),
        metadata={"tool_calls_count": 3},
    )
    r2 = EvaluationResult(
        evaluator_name="agentic",
        evaluator_version="1.0",
        case_id="c2",
        decision=Decision.REJECT,
        confidence=0.8,
        dimensions=DimensionScores.from_dict(dims),
        metadata={"tool_calls_count": 1},
    )
    r3 = EvaluationResult(
        evaluator_name="agentic",
        evaluator_version="1.0",
        case_id="c3",
        decision=Decision.ACCEPT,
        confidence=0.95,
        dimensions=DimensionScores.from_dict(dims),
        metadata={"tool_calls_count": 0},
    )

    records = [
        CaseRecord.from_result(
            r1,
            case_id="c1",
            case_kind="canonical",
            report_class="valid",
            expected_decision=Decision.ACCEPT,
        ),
        CaseRecord.from_result(
            r2,
            case_id="c2",
            case_kind="canonical",
            report_class="invalid",
            expected_decision=Decision.REJECT,
        ),
        CaseRecord.from_result(
            r3,
            case_id="c3",
            case_kind="canonical",
            report_class="valid",
            expected_decision=Decision.ACCEPT,
        ),
    ]

    metrics = compute_agentic_metrics(records)
    # Total calls: 3 + 1 + 0 = 4, average: 4 / 3 = 1.333
    assert metrics["total_tool_calls"] == 4.0
    assert metrics["avg_tool_calls"] == pytest.approx(1.333)
    # Cases with tools: 2 of 3 = 0.667
    assert metrics["tool_use_rate"] == pytest.approx(0.667)
