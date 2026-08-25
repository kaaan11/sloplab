"""Normalized evaluator-result contract models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sloplab.models.enums import DIMENSIONS, Decision, Severity


class Finding(BaseModel):
    """A single observation made by an evaluator."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    severity: Severity = Severity.MEDIUM
    evidence: str = ""
    message: str = ""


class DimensionScores(BaseModel):
    """Fixed five-dimension quality score vector; every value is within [0, 1]."""

    model_config = ConfigDict(extra="forbid")

    reproducibility: float = Field(ge=0.0, le=1.0)
    evidence_completeness: float = Field(ge=0.0, le=1.0)
    claim_evidence_consistency: float = Field(ge=0.0, le=1.0)
    impact_calibration: float = Field(ge=0.0, le=1.0)
    scope_consistency: float = Field(ge=0.0, le=1.0)

    def as_dict(self) -> dict[str, float]:
        return {
            DIMENSIONS[0]: self.reproducibility,
            DIMENSIONS[1]: self.evidence_completeness,
            DIMENSIONS[2]: self.claim_evidence_consistency,
            DIMENSIONS[3]: self.impact_calibration,
            DIMENSIONS[4]: self.scope_consistency,
        }

    @classmethod
    def from_dict(cls, values: dict[str, float]) -> DimensionScores:
        missing = [d for d in DIMENSIONS if d not in values]
        if missing:
            raise ValueError(f"missing dimension score(s): {missing}")
        return cls(**{d: values[d] for d in DIMENSIONS})


class EvaluationContext(BaseModel):
    """Harness-supplied context handed to evaluators.

    Evaluators must document which fields they rely on. The rules baseline uses only
    ``report``; the oracle uses only ``labels``. Label-bearing data must never be read
    by content-based evaluators.
    """

    model_config = ConfigDict(extra="forbid")

    report: Any  # ReportDocument; typed as Any to avoid circular import at runtime
    case_id: str
    labels: dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    """The single normalized output contract for all evaluators."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    evaluator_name: str = Field(min_length=1)
    evaluator_version: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    decision: Decision
    confidence: float = Field(ge=0.0, le=1.0)
    dimensions: DimensionScores
    findings: list[Finding] = Field(default_factory=list)
    rationale: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("findings")
    @classmethod
    def _check_finding_codes(cls, value: list[Finding]) -> list[Finding]:
        for finding in value:
            if not finding.code or finding.code != finding.code.upper():
                raise ValueError(f"finding codes must be UPPER_SNAKE_CASE; got {finding.code!r}")
        return value
