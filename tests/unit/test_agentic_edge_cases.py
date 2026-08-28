"""Edge case and resilience tests for Agentic triage evaluator and mock sandbox tools."""

from __future__ import annotations

from typing import Any

import pytest

from sloplab.evaluators.agentic import (
    AgentDecisionClient,
    AgenticTriageEvaluator,
    AgentStep,
    MockSandboxTools,
    ToolDefinition,
)
from sloplab.models.evaluation import EvaluationContext
from sloplab.models.report import ReportDocument


@pytest.fixture
def dummy_report() -> ReportDocument:
    return ReportDocument(
        fixture_id="dummy-001",
        path="dummy.md",
        raw_text="Dummy report content",
        title="Dummy",
        sections=(),
    )


def test_tool_execution_exception_handled_gracefully(dummy_report: ReportDocument) -> None:
    def failing_handler(**kwargs: Any) -> str:
        raise RuntimeError("Sandbox connection lost")

    failing_tool = ToolDefinition(
        name="failing_tool",
        description="A tool that always fails",
        handler=failing_handler,
    )

    class FailingClient(AgentDecisionClient):
        def __init__(self) -> None:
            self.called = False

        def plan_step(
            self,
            report_text: str,
            history: list[AgentStep],
            available_tools: list[ToolDefinition],
        ) -> tuple[AgentStep, bool]:
            if not self.called:
                self.called = True
                return (
                    AgentStep(thought="Calling failing tool", tool_name="failing_tool"),
                    False,
                )
            return (
                AgentStep(thought="Handling tool error, finalizing verdict", tool_name=None),
                True,
            )

    evaluator = AgenticTriageEvaluator(client=FailingClient(), tools=[failing_tool])
    ctx = EvaluationContext(report=dummy_report, case_id="case-fail", labels={})

    result = evaluator.evaluate(dummy_report, ctx)
    assert len(result.metadata["agent_trace"]) == 2
    # The first step should have an error observation
    step1 = result.metadata["agent_trace"][0]
    assert step1["tool"] == "failing_tool"


def test_unknown_tool_handled_gracefully(dummy_report: ReportDocument) -> None:
    class UnknownToolClient(AgentDecisionClient):
        def __init__(self) -> None:
            self.step = 0

        def plan_step(
            self,
            report_text: str,
            history: list[AgentStep],
            available_tools: list[ToolDefinition],
        ) -> tuple[AgentStep, bool]:
            self.step += 1
            if self.step == 1:
                return (
                    AgentStep(thought="Calling non-existent tool", tool_name="unregistered_tool"),
                    False,
                )
            return (
                AgentStep(thought="Done", tool_name=None),
                True,
            )

    evaluator = AgenticTriageEvaluator(client=UnknownToolClient())
    ctx = EvaluationContext(report=dummy_report, case_id="case-unknown-tool", labels={})

    result = evaluator.evaluate(dummy_report, ctx)
    assert result.metadata["tool_calls_count"] == 1


def test_agentic_zero_tool_calls_direct_verdict(dummy_report: ReportDocument) -> None:
    class DirectVerdictClient(AgentDecisionClient):
        def plan_step(
            self,
            report_text: str,
            history: list[AgentStep],
            available_tools: list[ToolDefinition],
        ) -> tuple[AgentStep, bool]:
            return (AgentStep(thought="Immediate rejection based on report alone"), True)

    evaluator = AgenticTriageEvaluator(client=DirectVerdictClient())
    ctx = EvaluationContext(report=dummy_report, case_id="case-direct", labels={})

    result = evaluator.evaluate(dummy_report, ctx)
    assert result.metadata["tool_calls_count"] == 0
    assert len(result.metadata["agent_trace"]) == 1


def test_mock_sandbox_tools_branches() -> None:
    # Test all branches in MockSandboxTools
    s1 = MockSandboxTools.search_source_tree("authz tenant middleware")
    assert "tenant_id verified" in s1

    s2 = MockSandboxTools.search_source_tree("completely_unrelated_symbol")
    assert "No matching source symbols" in s2

    p1 = MockSandboxTools.execute_poc_sandbox("curl http://test/endpoint/404")
    assert "404 Not Found" in p1

    p2 = MockSandboxTools.execute_poc_sandbox("random_command_that_times_out")
    assert "timed out" in p2
