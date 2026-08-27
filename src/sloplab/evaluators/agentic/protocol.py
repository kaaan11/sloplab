"""Agentic triage evaluator contract, tool definitions, and ReAct loop primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from sloplab import __version__
from sloplab.models.enums import Decision
from sloplab.models.evaluation import DimensionScores, EvaluationContext, EvaluationResult
from sloplab.models.report import ReportDocument


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    handler: Callable[..., str]


@dataclass
class AgentStep:
    thought: str
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    observation: str | None = None


class AgentDecisionClient(Protocol):
    """Protocol for an LLM client capable of ReAct multi-turn steps."""

    def plan_step(
        self,
        report_text: str,
        history: list[AgentStep],
        available_tools: list[ToolDefinition],
    ) -> tuple[AgentStep, bool]:
        """Return (next_step, is_final_verdict)."""
        ...  # pragma: no cover


class MockSandboxTools:
    """Standard mock sandbox tools provided to agentic evaluators."""

    @staticmethod
    def search_source_tree(query: str) -> str:
        """Mock searching codebase for vulnerable pattern or endpoint."""
        query_lower = query.lower()
        if "documentcontroller" in query_lower or "lookup" in query_lower:
            return (
                "Found match in controllers/document.py: "
                "def get(self, doc_id): return repo.find(doc_id)"
            )
        if "authz" in query_lower or "tenant" in query_lower:
            return "Found match in middleware/auth.py: tenant_id verified on session only"
        return "No matching source symbols found."

    @staticmethod
    def execute_poc_sandbox(command: str) -> str:
        """Mock executing a reproduction command in a clean sandbox."""
        if "404" in command:
            return "HTTP/1.1 404 Not Found"
        if "42" in command or "1042" in command or "curl" in command:
            return 'HTTP/1.1 200 OK\n{"id": 1042, "tenant": "B", "data": "secret"}'
        return "Execution timed out or command not recognized."


def default_agentic_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="search_source_tree",
            description="Search the application source tree for identifiers, routes, or symbols.",
            handler=MockSandboxTools.search_source_tree,
        ),
        ToolDefinition(
            name="execute_poc_sandbox",
            description="Execute a safe reproduction command or script inside an isolated sandbox.",
            handler=MockSandboxTools.execute_poc_sandbox,
        ),
    ]


class AgenticTriageEvaluator:
    """Autonomous multi-turn evaluator executing tools before emitting a triage verdict."""

    name = "agentic-triage"
    version = __version__

    def __init__(
        self,
        client: AgentDecisionClient,
        tools: list[ToolDefinition] | None = None,
        max_steps: int = 5,
    ) -> None:
        self.client = client
        self.tools = tools if tools is not None else default_agentic_tools()
        self.tool_map = {t.name: t.handler for t in self.tools}
        self.max_steps = max_steps

    def evaluate(
        self,
        report: ReportDocument,
        context: EvaluationContext,
    ) -> EvaluationResult:
        history: list[AgentStep] = []
        is_final = False

        for _ in range(self.max_steps):
            step, is_final = self.client.plan_step(report.raw_text, history, self.tools)
            if is_final or step.tool_name is None:
                history.append(step)
                break

            # Execute tool
            handler = self.tool_map.get(step.tool_name)
            if handler:
                try:
                    observation = handler(**step.tool_args)
                except Exception as exc:
                    observation = f"Tool execution error: {exc}"
            else:
                observation = f"Unknown tool: '{step.tool_name}'"

            step.observation = observation
            history.append(step)

        # Default dimensions for agentic verdict
        dims = {
            "reproducibility": 0.85
            if any(s.tool_name == "execute_poc_sandbox" for s in history)
            else 0.70,
            "evidence_completeness": 0.80,
            "claim_evidence_consistency": 0.80,
            "impact_calibration": 0.75,
            "scope_consistency": 0.75,
        }

        # Decision based on whether PoC confirmed or refuted
        has_poc_success = any(s.observation and "200 OK" in s.observation for s in history)
        decision = Decision.ACCEPT if has_poc_success else Decision.NEEDS_MANUAL_REVIEW

        steps_summary = [
            {"step": i + 1, "thought": s.thought, "tool": s.tool_name, "args": s.tool_args}
            for i, s in enumerate(history)
        ]

        return EvaluationResult(
            evaluator_name=self.name,
            evaluator_version=self.version,
            case_id=context.case_id,
            decision=decision,
            confidence=0.90 if has_poc_success else 0.60,
            dimensions=DimensionScores.from_dict(dims),
            findings=[],
            rationale=f"Agentic triage completed with {len(history)} step(s).",
            metadata={
                "tool_calls_count": sum(1 for s in history if s.tool_name is not None),
                "agent_trace": steps_summary,
            },
        )
