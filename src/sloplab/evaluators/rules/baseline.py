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
        r"no boundary [^.]*crossed",
        r"identifies none",
        r"no boundary between .+ is crossed",
        r"intended behavior",
        r"product preference",
        r"hardening (opportunity|suggestion)",
        r"cosmetic observation",
        r"usability tradeoff rather than a remediation",
    )
)

# Self-declared uncertainty. Reports that openly say their findings are unresolved
# should route to manual review rather than accept/reject. NOTE (v0.1.0): these
# patterns overlap with the phrasing style of this corpus's review-class fixtures;
# future corpora should include uncertain reports phrased differently so that
# baseline performance on them reflects generality rather than familiarity.
_UNCERTAINTY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"manual review requested",
        r"maintainer (?:confirmation|input|assistance|reproduction|ruling) requested",
        r"happy to coordinate",
        r"undetermined",
        r"inconclusive",
        r"unresolved",
        r"withheld pending",
        r"cannot (?:be |)(?:determined|established|confirmed|explained|classified)",
        r"could not (?:be )?(?:determined|conclusively determine)",
        r"unclear whether",
        r"severity cannot be (?:set|determined)",
        r"evidence is insufficient",
        r"insufficient to distinguish",
        r"genuinely unknown",
        r"hinges on undocumented",
    )
)

#: A boundary negation stated inside a conditional clause ("If X were enabled...")
# does not assert that the report's own subject crosses no boundary.
#: A boundary negation stated inside a conditional clause ("If X were enabled...")
# does not assert that the report's own subject crosses no boundary.
_CONDITIONAL_SENTENCE_RE = re.compile(r"\b(?:if|when|whether|unless)\b[^.?!]*$", re.IGNORECASE)

_CLAIM_CONTRADICTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"no bypass was demonstrated",
        r"both observed responses show",
        r"contradict",
        r"identical `?location`?",
        r"contain(s|ed)? no admin content",
        r"returned 403 forbidden and no cross-tenant data",
        r"could not reproduce any anomalous response",
        r"boundary held in every configuration",
    )
)

_UNVERIFIABLE_ATTRIBUTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"vendor has confirmed this issue as CVE-",
        r"previously disclosed and tracked as CVE-",
        r"tracking lists this defect as CVE-.*with fix status confirmed",
        r"fix status confirmed",
    )
)

_REFERENCE_STUFFING_PATTERN = re.compile(r"^#{1,3}\s+references\s*$", re.MULTILINE | re.IGNORECASE)
_NOISE_SECTION_PATTERN = re.compile(
    r"^#{1,3}\s+(additional context|background information)\s*$", re.MULTILINE | re.IGNORECASE
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
        # Boundary negations stated conditionally ("if profile B were exposed...")
        # do not assert the report's own subject is safe; they describe a
        # hypothetical and should route to review, not reject.
        no_boundary_matches = [m for rx in _NO_BOUNDARY_PATTERNS for m in rx.finditer(full)]
        conditional_negation = any(
            _CONDITIONAL_SENTENCE_RE.search(full[max(0, m.start() - 80) : m.start() + 1])
            for m in no_boundary_matches
        )
        unconditional_negation = bool(no_boundary_matches) and not conditional_negation
        contradiction_hits = _count_pattern_hits(full, _CLAIM_CONTRADICTION_PATTERNS)
        summary_claimed = bool(_STRONG_CLAIM_PATTERN.search(_section_text(report, "summary") or ""))

        if unconditional_negation:
            hit = next(
                (m.group(0) for rx in _NO_BOUNDARY_PATTERNS for m in [rx.search(full)] if m), ""
            )
            findings.append(
                Finding(
                    code="NO_SECURITY_BOUNDARY_STATED",
                    severity=Severity.HIGH,
                    evidence=hit[:80],
                )
            )
        elif conditional_negation:
            findings.append(
                Finding(code="CONDITIONAL_BOUNDARY_STATEMENT", severity=Severity.MEDIUM)
            )
        for hit in contradiction_hits[:1]:
            findings.append(
                Finding(
                    code="CLAIM_EVIDENCE_CONFLICT", severity=Severity.CRITICAL, evidence=hit[:80]
                )
            )
        if "affected_versions" in missing_core:
            findings.append(Finding(code="MISSING_AFFECTED_VERSIONS", severity=Severity.LOW))

        attribution_hits = _count_pattern_hits(full, _UNVERIFIABLE_ATTRIBUTION_PATTERNS)
        for hit in attribution_hits[:1]:
            findings.append(
                Finding(
                    code="ATTRIBUTION_CLAIM_UNVERIFIED",
                    severity=Severity.MEDIUM,
                    evidence=hit[:80],
                )
            )
        has_reference_section = bool(_REFERENCE_STUFFING_PATTERN.search(full))
        if has_reference_section:
            findings.append(Finding(code="UNVERIFIED_REFERENCE_BLOCK", severity=Severity.LOW))
        noise_sections = _NOISE_SECTION_PATTERN.findall(full)
        if noise_sections:
            findings.append(
                Finding(
                    code="TANGENTIAL_CONTENT_SECTION",
                    severity=Severity.INFO,
                    evidence=noise_sections[0],
                )
            )
        uncertainty_hits = _count_pattern_hits(full, _UNCERTAINTY_PATTERNS)
        if uncertainty_hits:
            findings.append(
                Finding(
                    code="SELF_DECLARED_UNCERTAINTY",
                    severity=Severity.MEDIUM,
                    evidence=uncertainty_hits[0][:80],
                )
            )

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
        penalty_attr = 0.3 * len(attribution_hits)
        consistency = max(0.0, 1.0 - penalty_fab - penalty_contra - penalty_attr)
        if summary_claimed and contradiction_hits:
            consistency = max(0.0, consistency - 0.15)

        completeness = present_ratio * 0.7 + (1.0 if not fab_hits else 0.6) * 0.3
        completeness = max(
            0.0,
            min(1.0, completeness - 0.05 * len(fab_hits) - (0.1 if has_reference_section else 0.0)),
        )

        calibration = 1.0 - 0.35 * bool(inflation_hits) - 0.1 * len(inflation_hits)
        if unconditional_negation and inflation_hits:
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
        # Manual-review signals: any fabrication/scope/inflation/attribution flag,
        # thin evidence, or mediocre dimension scores - anything that should stop
        # automation.
        quality_flags = (
            len(fab_hits)
            + len(scope_hits)
            + len(inflation_hits)
            + len(attribution_hits)
            + (1 if has_reference_section else 0)
        )
        noise_penalty = 0.02 * len(noise_sections)
        if consistency <= 0.45 or unconditional_negation or contradiction_hits:
            decision = Decision.REJECT
        elif (
            quality_flags > 0
            or reproducibility < 0.8 - noise_penalty
            or completeness < 0.8 - noise_penalty
            or overall < 0.78 - noise_penalty
        ):
            decision = Decision.NEEDS_MANUAL_REVIEW
        elif uncertainty_hits:
            # The report itself declares its conclusions unresolved; automation
            # should defer to humans regardless of structural quality.
            decision = Decision.NEEDS_MANUAL_REVIEW
        else:
            decision = Decision.ACCEPT

        if decision == Decision.ACCEPT:
            confidence = min(0.95, 0.5 + (overall - 0.78) * 1.6)
        elif decision == Decision.REJECT:
            confidence = min(0.9, 0.6 + max(0.0, 0.45 - consistency) * 0.5)
        else:
            confidence = 0.45 if not uncertainty_hits else 0.5

        rationale_parts = [
            f"missing_core_sections={len(missing_core)}",
            f"steps={step_count}",
            f"fabrication_hits={len(fab_hits)}",
            f"scope_expansion_hits={len(scope_hits)}",
            f"inflation_hits={len(inflation_hits)}",
            f"attribution_hits={len(attribution_hits)}",
            f"reference_block={has_reference_section}",
            f"noise_sections={len(noise_sections)}",
            f"uncertainty={len(uncertainty_hits)}",
            f"no_boundary={unconditional_negation} cond_boundary={conditional_negation}",
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
