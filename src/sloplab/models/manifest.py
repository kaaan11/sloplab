"""Manifest schemas for canonical fixtures and derived mutation cases."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sloplab.models.enums import (
    DIMENSIONS,
    Decision,
    ImpactClass,
    MutationCategory,
    ReportClass,
    canonical_expected_decision,
)


class StrictModel(BaseModel):
    """Base model: unknown fields are schema errors with actionable messages."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ReportRef(StrictModel):
    """Pointer to the Markdown file belonging to a manifest."""

    path: str = Field(min_length=1)


class GroundTruth(StrictModel):
    """Human-authored ground truth for a canonical fixture."""

    reproducible: bool | None = None
    impact_class: ImpactClass | None = None
    required_evidence: list[str] = Field(default_factory=list)
    disallowed_claims: list[str] = Field(default_factory=list)
    expected_dimensions: dict[str, float] = Field(default_factory=dict)
    rationale: str = ""

    @field_validator("expected_dimensions")
    @classmethod
    def _check_dimensions(cls, value: dict[str, float]) -> dict[str, float]:
        unknown = set(value) - set(DIMENSIONS)
        if unknown:
            raise ValueError(
                f"unknown dimension(s) {sorted(unknown)}; expected subset of {list(DIMENSIONS)}"
            )
        out_of_range = {k: v for k, v in value.items() if not 0.0 <= v <= 1.0}
        if out_of_range:
            raise ValueError(f"dimension scores must be within [0, 1]; got {out_of_range}")
        return value


class CanonicalManifest(StrictModel):
    """Manifest describing one canonical fixture directory."""

    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^canonical-[a-z0-9]+(-[a-z0-9]+)*$")
    title: str = Field(min_length=3)
    source_type: Literal["synthetic"] = "synthetic"
    license: str = "CC0-1.0"
    report_class: ReportClass
    pair_id: str | None = None
    ground_truth: GroundTruth
    report: ReportRef
    sanitization_note: str = ""

    @model_validator(mode="after")
    def _check_pair(self) -> CanonicalManifest:
        if self.report_class == ReportClass.PRESENTATION_PAIR and not self.pair_id:
            raise ValueError(
                f"manifest {self.id!r}: report_class 'presentation_pair' requires 'pair_id'"
            )
        return self

    def expected_decision(self) -> Decision:
        """Ground-truth triage decision for this canonical fixture."""
        if self.report_class == ReportClass.PRESENTATION_PAIR:
            # Presentation pairs encode their class in ground truth rationale via
            # pair membership; harness resolves using the sibling's class.
            return Decision.NEEDS_MANUAL_REVIEW  # overridden by harness when paired
        return canonical_expected_decision(self.report_class)


class ExpectedEffect(StrictModel):
    """Descriptive (human-readable) effect of a mutation; scoring uses expected_decision."""

    report_validity: Literal["unchanged", "degraded"] = "unchanged"
    claim_quality: Literal["unchanged", "degraded"] = "unchanged"
    presentation_strength: Literal["unchanged", "increased"] = "unchanged"


class MutationManifest(StrictModel):
    """Provenance manifest for one derived (mutated) fixture."""

    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^mut-[a-z0-9]+(-[a-z0-9]+)*$")
    parent_id: str = Field(pattern=r"^canonical-[a-z0-9]+(-[a-z0-9]+)*$")
    operator: str = Field(min_length=1)
    category: MutationCategory
    parameters: dict[str, Any] = Field(default_factory=dict)
    seed: int = Field(ge=0)
    variant_index: int = Field(ge=0)
    base_seed: int = Field(ge=0)
    expected_decision: Decision
    expected_effect: ExpectedEffect = ExpectedEffect()
    expected_dimensions: dict[str, float] = Field(default_factory=dict)
    generator_version: str
    report: ReportRef

    @field_validator("expected_dimensions")
    @classmethod
    def _check_dimensions(cls, value: dict[str, float]) -> dict[str, float]:
        unknown = set(value) - set(DIMENSIONS)
        if unknown:
            raise ValueError(
                f"unknown dimension(s) {sorted(unknown)}; expected subset of {list(DIMENSIONS)}"
            )
        out_of_range = {k: v for k, v in value.items() if not 0.0 <= v <= 1.0}
        if out_of_range:
            raise ValueError(f"dimension scores must be within [0, 1]; got {out_of_range}")
        return value
