"""Evidence-graph baseline evaluator (NEGATIVE CONTROL).

This evaluator is a deliberate **negative control**, not a competitive baseline:
it models structure-only triage and is intentionally blind to content-quality
mutations. Its poor detection/FAR numbers in studies demonstrate that SlopLab
detects such blindness.

A deterministic, label-independent model of the minimal claim-evidence graph
every credible vulnerability report must contain:

    Impact claim
      |- supported by an affected-component statement
      |- supported by reproduction evidence (ordered steps + observed result)
      '- consistent with the security-boundary statement

Unlike the rules baseline (flat lexical heuristics), this evaluator first extracts
graph nodes and edges, scores dimensions from edge completeness, and derives its
decision from structural outcomes. It never reads ``context.labels``.

Documented limitations: node detection is lexical; a report whose sections are
renamed beyond the shared conventions yields missing nodes rather than clever
matching. This is deliberate - the evaluator is a comparable baseline, not a
strong system.
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


class GraphNode:
    IMPACT_CLAIM = "impact_claim"
    COMPONENT_REF = "component_ref"
    REPRO_EVIDENCE = "repro_evidence"
    OBSERVED_RESULT = "observed_result"
    BOUNDARY_STATEMENT = "boundary_statement"


_SEVERITY_WORDS = re.compile(r"\b(critical|high|medium|low|severe|moderate|minor)\b", re.IGNORECASE)
_CONSEQUENCE_WORDS = re.compile(
    r"\b(disclosure|bypass\w*|injection|takeover|exposure|compromise\w*|tamper\w*|"
    r"escalation|denial|unauthorized|unauthenticated|forg\w*|leak\w*|reveal\w*|"
    r"allow\w*|accept\w*|skip\w*|persist\w*|execut\w*)\b",
    re.IGNORECASE,
)

_NO_BOUNDARY_MARKERS = re.compile(
    r"\b(no security boundary|does not identify one|identifies none|"
    r"no boundary[^.]*crossed|intended behavior|product preference)\b",
    re.IGNORECASE,
)

_HEDGED_UNRESOLVED = re.compile(
    r"\b(undetermined|unclear whether|cannot be determined|manual review requested)\b",
    re.IGNORECASE,
)

#: Observation prose that undermines rather than supports the claimed consequence.
#: An edge named "supports" must break when the report's own observation contradicts
#: its summary claim (contract conformance; see V26 results audit).
_UNDERMINES_CLAIM = re.compile(
    r"\b(however|could not reproduce|contradict\w*|behaved identically|"
    r"boundary held|no \w+ was returned|returned 403)\b",
    re.IGNORECASE,
)

#: Full reproduction support requires at least two ordered steps plus an observed
#: result; fewer steps weaken the edge below acceptance strength.
MIN_SUPPORT_STEPS = 2


def _section(report: ReportDocument, key: str) -> str:
    return report.section_text(EVIDENCE_SECTION_PATTERNS[key])


class EvidenceGraphBaselineEvaluator:
    name = "evidence-graph-baseline"
    version = "0.2.0"

    def evaluate(
        self,
        report: ReportDocument,
        context: EvaluationContext,
    ) -> EvaluationResult:
        _ = context  # content-only: labels deliberately unused
        findings: list[Finding] = []

        # ---- extract nodes -------------------------------------------------
        # An impact claim exists when calibrated-severity or consequence language
        # appears in the Summary or Impact prose (claims live there by convention).
        impact_text = _section(report, "summary")
        if not (_SEVERITY_WORDS.search(impact_text) or _CONSEQUENCE_WORDS.search(impact_text)):
            impact_heading_match = report.find_sections(r"\bimpact\b")
            impact_prose = "\n".join(s.text for s in impact_heading_match)
            impact_claims = bool(
                _SEVERITY_WORDS.search(impact_prose) or _CONSEQUENCE_WORDS.search(impact_prose)
            )
        else:
            impact_claims = True

        component_text = _section(report, "affected_component")
        component_node = bool(component_text.strip())

        repro_section = next(
            (
                s
                for s in report.sections
                if s.heading
                and re.search(EVIDENCE_SECTION_PATTERNS["reproduction_steps"], s.heading, re.I)
            ),
            None,
        )
        step_count = len(numbered_steps(repro_section)) if repro_section else 0
        observed_text = _section(report, "observed_result")
        repro_node = step_count >= 1 and bool(observed_text.strip())
        observed_node = bool(observed_text.strip())
        observed_undermines = bool(observed_text) and bool(_UNDERMINES_CLAIM.search(observed_text))

        boundary_text = _section(report, "expected_security_boundary")
        boundary_negated = bool(boundary_text) and bool(_NO_BOUNDARY_MARKERS.search(boundary_text))
        boundary_node = bool(boundary_text.strip())

        hedged = bool(_HEDGED_UNRESOLVED.search(report.raw_text))

        # ---- edges ----------------------------------------------------------
        # Edge semantics are directional: an observation that undermines the claim
        # does not count as support (contract conformance).
        e1 = impact_claims and component_node  # claim <- component
        e2 = (
            impact_claims and step_count >= MIN_SUPPORT_STEPS and bool(observed_text.strip())
        )  # claim <- reproduction
        e3 = impact_claims and observed_node and not observed_undermines
        e4 = (
            impact_claims and boundary_node and not boundary_negated  # claim ~ boundary consistency
        )

        edges_present = sum(1 for e in (e1, e2, e3, e4) if e)

        for code, present in (
            ("GRAPH_MISSING_IMPACT_CLAIM", impact_claims),
            ("GRAPH_MISSING_COMPONENT_SUPPORT", e1),
            ("GRAPH_MISSING_REPRO_SUPPORT", e2),
            ("GRAPH_MISSING_OBSERVED_SUPPORT", e3),
            ("GRAPH_BOUNDARY_CONTRADICTS_CLAIM", e4),
        ):
            if not present:
                findings.append(Finding(code=code, severity=Severity.MEDIUM))

        if boundary_negated or observed_undermines:
            # negated boundary OR self-undermining observation: the report's own
            # content defeats its claim -> reject.
            findings.append(
                Finding(
                    code="BOUNDARY_NEGATED_BY_AUTHOR",
                    severity=Severity.HIGH,
                    evidence=(boundary_text[:80]),
                )
            )
        if observed_undermines:
            hit = _UNDERMINES_CLAIM.search(observed_text)
            findings.append(
                Finding(
                    code="GRAPH_OBSERVED_UNDERMINES_CLAIM",
                    severity=Severity.HIGH,
                    evidence=hit.group(0) if hit else "",
                )
            )
        if repro_section is not None and 0 < step_count < MIN_SUPPORT_STEPS + 1:
            findings.append(
                Finding(
                    code="GRAPH_THIN_REPRO_SUPPORT",
                    severity=Severity.LOW,
                    message=f"only {step_count} ordered step(s)",
                )
            )

        # ---- dimension scoring ---------------------------------------------
        support_ratio = edges_present / 4
        reproducibility = min(1.0, min(step_count, 3) / 3 * 0.7 + (0.3 if e2 else 0.0))
        completeness = round(0.25 * e1 + 0.35 * e2 + 0.2 * e3 + 0.2 * support_ratio, 3)
        consistency = round((0.45 if e4 else 0.15) + (0.2 if e2 else 0.0), 3)
        calibration = round(min(1.0, 0.5 + 0.5 * support_ratio - (0.25 if hedged else 0.0)), 3)
        scope = round(
            min(1.0, (1.0 if component_node else 0.3) * (0.8 if boundary_node else 0.5)), 3
        )

        dims = {
            REPRODUCIBILITY: reproducibility,
            EVIDENCE_COMPLETENESS: completeness,
            CLAIM_EVIDENCE_CONSISTENCY: consistency,
            IMPACT_CALIBRATION: calibration,
            SCOPE_CONSISTENCY: scope,
        }
        overall = sum(dims[d] for d in DIMENSIONS) / len(DIMENSIONS)

        # ---- decision policy ------------------------------------------------
        # Precedence: hard-reject on negated boundary; never accept a report that
        # declares itself unresolved; a complete, strong graph may accept.
        if boundary_negated or observed_undermines:
            decision = Decision.REJECT
        elif hedged:
            decision = Decision.NEEDS_MANUAL_REVIEW
        elif impact_claims and edges_present == 4 and overall >= 0.75:
            decision = Decision.ACCEPT
        else:
            decision = Decision.NEEDS_MANUAL_REVIEW

        confidence = {
            Decision.ACCEPT: min(0.95, 0.55 + (overall - 0.75)),
            Decision.REJECT: 0.85,
            Decision.NEEDS_MANUAL_REVIEW: 0.5,
        }[decision]

        rationale = (
            f"evidence-graph: claims={impact_claims} component={component_node} "
            f"repro={repro_node}(steps={step_count}) observed={observed_node} "
            f"boundary={boundary_node}(negated={boundary_negated}) "
            f"edges={edges_present}/4 hedged={hedged} overall={overall:.2f}"
        )
        return EvaluationResult(
            evaluator_name=self.name,
            evaluator_version=self.version,
            case_id=context.case_id,
            decision=decision,
            confidence=round(max(0.05, min(confidence, 0.99)), 3),
            dimensions=DimensionScores.from_dict(dims),
            findings=findings,
            rationale=f"{self.name}: {rationale}",
            metadata={"heuristic_version": self.version, "edges": edges_present},
        )
