"""Pydantic schemas for all SlopLab structured data."""

from sloplab.models.enums import (
    DIMENSIONS,
    Decision,
    ImpactClass,
    MutationCategory,
    ReportClass,
    Severity,
    canonical_expected_decision,
)
from sloplab.models.evaluation import DimensionScores, EvaluationContext, EvaluationResult, Finding
from sloplab.models.manifest import CanonicalManifest, ExpectedEffect, GroundTruth, MutationManifest
from sloplab.models.report import ReportDocument, ReportSection, SourceLocation
from sloplab.models.run import CaseRecord, EvaluatorInfo, RunMetadata
from sloplab.models.suite import ClassPolicy, SuiteConfig

__all__ = [
    "DIMENSIONS",
    "CanonicalManifest",
    "CaseRecord",
    "ClassPolicy",
    "Decision",
    "DimensionScores",
    "EvaluationContext",
    "EvaluationResult",
    "ExpectedEffect",
    "EvaluatorInfo",
    "Finding",
    "GroundTruth",
    "ImpactClass",
    "MutationCategory",
    "MutationManifest",
    "ReportClass",
    "ReportDocument",
    "ReportSection",
    "RunMetadata",
    "Severity",
    "SourceLocation",
    "SuiteConfig",
    "canonical_expected_decision",
]
