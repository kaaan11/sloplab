"""Core enumerations shared across SlopLab."""

from __future__ import annotations

from enum import StrEnum

REPRODUCIBILITY = "reproducibility"
EVIDENCE_COMPLETENESS = "evidence_completeness"
CLAIM_EVIDENCE_CONSISTENCY = "claim_evidence_consistency"
IMPACT_CALIBRATION = "impact_calibration"
SCOPE_CONSISTENCY = "scope_consistency"

#: Fixed quality dimensions scored by every evaluator (normalized contract).
DIMENSIONS: tuple[str, ...] = (
    REPRODUCIBILITY,
    EVIDENCE_COMPLETENESS,
    CLAIM_EVIDENCE_CONSISTENCY,
    IMPACT_CALIBRATION,
    SCOPE_CONSISTENCY,
)


class Decision(StrEnum):
    """Normalized triage decision produced by every evaluator."""

    ACCEPT = "accept"
    REJECT = "reject"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"


class ReportClass(StrEnum):
    """Ground-truth class of a canonical fixture."""

    VALID = "valid"
    INVALID = "invalid"
    REVIEW = "review"
    PRESENTATION_PAIR = "presentation_pair"


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactClass(StrEnum):
    NONE = "none"
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MutationCategory(StrEnum):
    EVIDENCE_REMOVAL = "evidence_removal"
    EVIDENCE_CONTRADICTION = "evidence_contradiction"
    IMPACT = "impact"
    TECHNICAL_CONSISTENCY = "technical_consistency"
    REFERENCE = "reference"
    PRESENTATION = "presentation"
    NOISE = "noise"


CANONICAL_EXPECTED_DECISION: dict[ReportClass, Decision] = {
    ReportClass.VALID: Decision.ACCEPT,
    ReportClass.INVALID: Decision.REJECT,
    ReportClass.REVIEW: Decision.NEEDS_MANUAL_REVIEW,
    # Presentation-pair members carry their own expected decision via ground truth;
    # the plain member defaults like a normal class below.
}


def canonical_expected_decision(report_class: ReportClass) -> Decision:
    """Default expected triage decision for a canonical fixture class."""
    return CANONICAL_EXPECTED_DECISION.get(report_class, Decision.NEEDS_MANUAL_REVIEW)
