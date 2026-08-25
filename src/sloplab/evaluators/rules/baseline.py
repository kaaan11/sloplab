"""Deterministic rules-based evaluator baseline.

This evaluator inspects ONLY the report text (never harness labels). It applies
transparent heuristics over section structure and language patterns.

Documented limitations (by design - this is a baseline to beat, not a strong system):
- It cannot verify technical claims; "fabrication" signals are lexical only.
- It cannot distinguish a genuinely invalid report from a well-written valid one
  when no boundary-crossing statement is present.
- It is intentionally sensitive to the exact phrases SlopLab operators insert,
  because those phrases model common low-quality-report patterns. Real evaluators
  should not be tuned to this corpus.
"""

from __future__ import annotations

import re

from sloplab.corpus.conventions import EVIDENCE_SECTION_PATTERNS
from sloplab.models.enums import (
    CLAIM_EVIDENCE_CONSISTENCY,
    DIMENSIONS,
    EVIDENCE_COMPLETENESS,
    IMPACT_CALIBRATION,
    REPRODUCIBILITY,
    SCOPE_CONSISTENCY,
    Decision,
    Severity,
)
from sloplab.models.evaluation import DimensionScores, EvaluationContext, EvaluationResult, Finding
from sloplab.models.report import ReportDocument
from sloplab.mutations.textops import numbered_steps

_CORE_SECTION_KEYS: tuple[str, ...] = (
    "summary",
    "affected_component",
    "affected_versions",
    "preconditions",
    "reproduction_steps",
    "observed_result",
    "expected_security_boundary",
)

_FABRICATION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"assigns? this issue advisory",
        r"matches the vendor advisory identifier",
        r"according to the deployment manifest used during testing",
        r"referenced in the component changelog",
    )
)

_SCOPE_EXPANSION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"every version ever released",
        r"all earlier releases since \d+\.\d+\.\d+ and all future releases",
        r"including builds distributed through unofficial mirrors",
        r"also present in the administrative api",
        r"including batch jobs and internal tooling",
    )
)

_INFLATION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"actively exploited data breach",
        r"fully compromise the entire platform",
        r"confirmed mass scanning in the wild",
        r"exposes every customer record",
        r"emergency response is required",
    )
)

_NO_BOUNDARY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"no security boundary",
        r"does not identify one",
        r"no boundary .* is crossed",
        r"no boundary between .+ is crossed",
        r"intended behavior",
        r"product preference",
        r"hardening (opportunity|suggestion)",
        r"cosmetic observation",
    )
)

_CLAIM_CONTRADICTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"no bypass was demonstrated",
        r"both observed responses show",
        r"contradict",
        r"identical `?location`?",
        r"contain(s|ed)? no admin content",
    )
)

_STRONG_CLAIM_PATTERN = re.compile(
    r"bypass|compromise|exposes|breach|takeover|disclosure", re.IGNORECASE
)


def _section_text(report: ReportDocument, key: str) -> str:
    pattern = EVIDENCE_SECTION_PATTERNS[key]
    return report.section_text(pattern)


def _count_pattern_hits(text: str, patterns: tuple[re.Pattern[str], ...]) -> list[str]:
    hits: list[str] = []
    for rx in patterns:
        match = rx.search(text)
        if match:
            hits.append(match.group(0))
    return hits


class RulesBaselineEvaluator:
    name = "rules-baseline"
    version = "0.1.0"

    def evaluate(
        self,
        report: ReportDocument,
        context: EvaluationContext,
    ) -> EvaluationResult:
        _ = context  # content-only evaluator: labels deliberately unused
        findings: list[Finding] = []
        full = report.raw_text

        # --- structural evidence ---
        missing_core = [
            k for k in _CORE_SECTION_KEYS if not report.find_sections(EVIDENCE_SECTION_PATTERNS[k])
        ]
        for key in missing_core:
            findings.append(
                Finding(code=f"MISSING_SECTION_{key.upper()}", severity=Severity.MEDIUM)
            )

        repro_section = None
        for s in report.sections:
            if s.heading and re.search(
                EVIDENCE_SECTION_PATTERNS["reproduction_steps"], s.heading, re.I
            ):
                repro_section = s
                break
        step_count = len(numbered_steps(repro_section)) if repro_section else 0
        if repro_section is not None and step_count == 0:
            findings.append(Finding(code="EMPTY_REPRO_STEPS", severity=Severity.HIGH))
        elif step_count < 3 and repro_section is not None:
            findings.append(Finding(code="THIN_REPRO_STEPS", severity=Severity.MEDIUM))

        # --- fabrication / scope / inflation signals ---
        fab_hits = _count_pattern_hits(full, _FABRICATION_PATTERNS)
        for hit in fab_hits:
            findings.append(
                Finding(
                    code="FABRICATED_IDENTIFIER_CLAIM",
                    severity=Severity.HIGH,
                    evidence=hit[:80],
                )
            )

        scope_hits = _count_pattern_hits(full, _SCOPE_EXPANSION_PATTERNS)
        for hit in scope_hits[:1]:
            findings.append(
                Finding(code="SCOPE_EXPANSION_CLAIM", severity=Severity.MEDIUM, evidence=hit[:80])
            )

        inflation_hits = _count_pattern_hits(full, _INFLATION_PATTERNS)
        for hit in inflation_hits[:1]:
            findings.append(
                Finding(
                    code="IMPACT_INFLATION_LANGUAGE",
                    severity=Severity.MEDIUM,
                    evidence=hit[:80],
                )
            )

        # --- boundary / validity reasoning ---
        boundary_text = report.section_text(EVIDENCE_SECTION_PATTERNS["expected_security_boundary"])
        no_boundary_hits = _count_pattern_hits(full, _NO_BOUNDARY_PATTERNS)
        contradiction_hits = _count_pattern_hits(full, _CLAIM_CONTRADICTION_PATTERNS)
        summary_claimed = bool(_STRONG_CLAIM_PATTERN.search(_section_text(report, "summary") or ""))

        for hit in no_boundary_hits[:1]:
            findings.append(
                Finding(
                    code="NO_SECURITY_BOUNDARY_STATED", severity=Severity.HIGH, evidence=hit[:80]
                )
            )
        for hit in contradiction_hits[:1]:
            findings.append(
                Finding(
                    code="CLAIM_EVIDENCE_CONFLICT", severity=Severity.CRITICAL, evidence=hit[:80]
                )
            )
        if "affected_versions" in missing_core:
            findings.append(Finding(code="MISSING_AFFECTED_VERSIONS", severity=Severity.LOW))

        # --- dimension scoring (transparent arithmetic) ---
        present_ratio = 1.0 - len(missing_core) / len(_CORE_SECTION_KEYS)
        if repro_section is None:
            step_score = 0.05
        elif step_count == 0:
            step_score = 0.1
        elif step_count == 1:
            step_score = 0.35
        elif step_count == 2:
            step_score = 0.65
        else:
            step_score = 1.0
        reproducibility = min(1.0, present_ratio * 0.35 + step_score * 0.65)

        penalty_fab = 0.45 * len(fab_hits)
        penalty_contra = 0.55 * len(contradiction_hits)
        consistency = max(0.0, 1.0 - penalty_fab - penalty_contra)
        if summary_claimed and contradiction_hits:
            consistency = max(0.0, consistency - 0.15)

        completeness = present_ratio * 0.7 + (1.0 if not fab_hits else 0.6) * 0.3
        completeness = max(0.0, min(1.0, completeness - 0.05 * len(fab_hits)))

        calibration = 1.0 - 0.35 * bool(inflation_hits) - 0.1 * len(inflation_hits)
        if no_boundary_hits and inflation_hits:
            calibration -= 0.2
        calibration = max(0.0, calibration)

        scope = 1.0 - 0.4 * bool(scope_hits) - 0.25 * ("affected_versions" in missing_core)
        scope = max(0.0, min(1.0, scope))

        dims = {
            REPRODUCIBILITY: round(reproducibility, 3),
            EVIDENCE_COMPLETENESS: round(completeness, 3),
            CLAIM_EVIDENCE_CONSISTENCY: round(consistency, 3),
            IMPACT_CALIBRATION: round(calibration, 3),
            SCOPE_CONSISTENCY: round(scope, 3),
        }

        overall = sum(dims[d] for d in DIMENSIONS) / len(DIMENSIONS)

        # --- decision policy (documented thresholds) ---
        # Hard-reject signals: explicit no-boundary statements, claim/evidence
        # contradictions, or collapsed consistency.
        # Manual-review signals: any fabrication/scope/inflation flag, thin evidence,
        # or mediocre dimension scores - anything that should stop automation.
        quality_flags = len(fab_hits) + len(scope_hits) + len(inflation_hits)
        if consistency <= 0.45 or no_boundary_hits or contradiction_hits:
            decision = Decision.REJECT
        elif quality_flags > 0 or reproducibility < 0.8 or completeness < 0.8 or overall < 0.78:
            decision = Decision.NEEDS_MANUAL_REVIEW
        else:
            decision = Decision.ACCEPT

        if decision == Decision.ACCEPT:
            confidence = min(0.95, 0.5 + (overall - 0.78) * 1.6)
        elif decision == Decision.REJECT:
            confidence = min(0.9, 0.6 + max(0.0, 0.45 - consistency) * 0.5)
        else:
            confidence = 0.45

        rationale_parts = [
            f"missing_core_sections={len(missing_core)}",
            f"steps={step_count}",
            f"fabrication_hits={len(fab_hits)}",
            f"scope_expansion_hits={len(scope_hits)}",
            f"inflation_hits={len(inflation_hits)}",
            f"no_boundary={bool(no_boundary_hits)}",
            f"contradiction={bool(contradiction_hits)}",
            f"overall={overall:.2f}",
        ]
        return EvaluationResult(
            evaluator_name=self.name,
            evaluator_version=self.version,
            case_id=context.case_id,
            decision=decision,
            confidence=round(max(0.05, min(confidence, 0.99)), 3),
            dimensions=DimensionScores.from_dict(dims),
            findings=findings,
            rationale="rules-baseline: " + "; ".join(rationale_parts),
            metadata={"heuristic_version": self.version},
        )
