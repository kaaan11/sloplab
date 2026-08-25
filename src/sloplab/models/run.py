"""Run metadata and per-case result records for benchmark runs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from sloplab.models.enums import Decision
from sloplab.models.evaluation import EvaluationResult


class EvaluatorInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RunMetadata(BaseModel):
    """Provenance header for a benchmark run; recorded as the first JSONL line."""

    model_config = ConfigDict(extra="forbid")

    record_type: Literal["run_metadata"] = "run_metadata"
    run_id: str = Field(min_length=1)
    sloplab_version: str
    python_version: str
    git_commit: str | None = None
    suite_name: str
    suite_hash: str
    suite_config: dict[str, Any] = Field(default_factory=dict)
    base_seed: int
    evaluators: list[EvaluatorInfo]
    started_at: datetime = Field(default_factory=_utcnow)


class CaseRecord(BaseModel):
    """One evaluated case (canonical or mutated) by one evaluator."""

    model_config = ConfigDict(extra="forbid")

    record_type: Literal["case"] = "case"
    case_id: str
    case_kind: Literal["canonical", "mutated"]
    parent_id: str | None = None
    operator: str | None = None
    report_class: str
    expected_decision: Decision | None
    evaluator_name: str
    evaluator_version: str
    decision: Decision
    confidence: float
    dimensions: dict[str, float]
    correct: bool
    findings: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""
    evaluation_metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_result(
        cls,
        result: EvaluationResult,
        *,
        case_id: str,
        case_kind: Literal["canonical", "mutated"],
        report_class: str,
        expected_decision: Decision | None,
        parent_id: str | None = None,
        operator: str | None = None,
    ) -> CaseRecord:
        return cls(
            case_id=case_id,
            case_kind=case_kind,
            parent_id=parent_id,
            operator=operator,
            report_class=report_class,
            expected_decision=expected_decision,
            evaluator_name=result.evaluator_name,
            evaluator_version=result.evaluator_version,
            decision=result.decision,
            confidence=result.confidence,
            dimensions=result.dimensions.as_dict(),
            correct=(expected_decision is not None and result.decision == expected_decision),
            findings=[f.model_dump() for f in result.findings],
            rationale=result.rationale,
            evaluation_metadata=result.metadata,
        )
