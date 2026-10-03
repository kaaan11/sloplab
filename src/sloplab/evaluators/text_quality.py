"""Offline lexical quality control, with no claim-validity inference.

Measures section content and ordered-step detail. Lexical overlap/repetition are
diagnostics, not evidence of truth. All decisions route to manual review; three
semantic dimensions stay at the contract's neutral 0.5, marked as unassessed.
No fitted vocabulary, model, network access, corpus labels or operator phrases.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterator
from itertools import islice

from sloplab.corpus.conventions import EVIDENCE_SECTION_PATTERNS
from sloplab.models.enums import Decision, Severity
from sloplab.models.evaluation import (
    DimensionScores,
    EvaluationContext,
    EvaluationResult,
    Finding,
)
from sloplab.models.report import ReportDocument, ReportSection

_TOKEN_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")
_STEP_RE = re.compile(r"^[ \t]{0,3}\d+[.)][ \t]+(?P<body>\S.*)$")
_LIST_PREFIX_RE = re.compile(r"^[ \t]{0,3}\d+[.)][ \t]+", re.MULTILINE)
_FENCE_RE = re.compile(r"^[ \t]*(?P<marker>`{3,}|~{3,})(?P<tail>.*)$")
_STOP_WORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "but",
        "by",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "his",
        "i",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "our",
        "she",
        "that",
        "the",
        "their",
        "them",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "we",
        "were",
        "will",
        "with",
        "you",
        "your",
    ]
)
_SECTION_TARGETS = {
    "summary": 6,
    "affected_component": 1,
    "affected_versions": 1,
    "preconditions": 6,
    "reproduction_steps": 6,
    "observed_result": 6,
    "expected_security_boundary": 6,
}
_UNASSESSED = (
    "claim_evidence_consistency",
    "impact_calibration",
    "scope_consistency",
)


def _tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return _TOKEN_RE.findall(_LIST_PREFIX_RE.sub("", normalized))


def _content_tokens(text: str) -> list[str]:
    return [token for token in _tokens(text) if token not in _STOP_WORDS]


def _body(section: ReportSection) -> str:
    lines = section.text.splitlines()
    return "\n".join(lines[1:] if section.heading is not None else lines)


def _core_bodies(report: ReportDocument) -> dict[str, str]:
    """Include child sections; heading text never supplies content tokens."""
    bodies = {}
    for key in _SECTION_TARGETS:
        pattern = re.compile(EVIDENCE_SECTION_PATTERNS[key], re.IGNORECASE)
        chunks = []
        for index, section in enumerate(report.sections):
            if section.heading is None or not pattern.search(section.heading):
                continue
            chunks.append(_body(section))
            for child in islice(report.sections, index + 1, None):
                if child.level <= section.level:
                    break
                chunks.append(_body(child))
        bodies[key] = "\n".join(chunks)
    return bodies


def _outside_fences(text: str) -> Iterator[str]:
    """Mirror parser fence markers, including longer/mismatched closing fences."""
    marker = ""
    length = 0
    for line in text.splitlines():
        fence = _FENCE_RE.match(line)
        if fence:
            current = fence["marker"]
            if not marker:
                marker, length = current[0], len(current)
            elif current[0] == marker and len(current) >= length and not fence["tail"].strip():
                marker, length = "", 0
            continue
        if not marker:
            yield line


def _ordered_steps(text: str) -> list[tuple[str, ...]]:
    return [
        tuple(_content_tokens(match["body"]))
        for line in _outside_fences(text)
        if (match := _STEP_RE.match(line)) is not None
    ]


def _cosine(left: str, right: str) -> float | None:
    """Term-frequency cosine. Sorted integer sums make it repeatable."""
    a, b = Counter(_content_tokens(left)), Counter(_content_tokens(right))
    if not a or not b:
        return None
    numerator = sum(a[t] * b[t] for t in sorted(a.keys() & b.keys()))
    denominator = math.sqrt(sum(n * n for n in a.values()) * sum(n * n for n in b.values()))
    return round(min(1.0, numerator / denominator), 6)


class TextQualityBaselineEvaluator:
    """Transparent text-quality proxies and an always-review decision control."""

    name = "text-quality-baseline"
    version = "0.1.0"
    requires_labels = False

    def evaluate(self, report: ReportDocument, context: EvaluationContext) -> EvaluationResult:
        bodies = _core_bodies(report)
        unique_tokens = {key: len(set(_tokens(body))) for key, body in bodies.items()}
        section_scores = {
            key: min(unique_tokens[key] / target, 1.0) for key, target in _SECTION_TARGETS.items()
        }
        findings = []
        for key, target in _SECTION_TARGETS.items():
            if unique_tokens[key] == 0:
                present = bool(report.find_sections(EVIDENCE_SECTION_PATTERNS[key]))
                findings.append(
                    Finding(
                        code=f"TEXT_{'EMPTY' if present else 'MISSING'}_{key.upper()}",
                        severity=Severity.MEDIUM,
                        message="No body tokens in this report section.",
                    )
                )
            elif unique_tokens[key] < target:
                findings.append(
                    Finding(
                        code=f"TEXT_SPARSE_{key.upper()}",
                        severity=Severity.LOW,
                        message=f"Fewer than {target} distinct body tokens; lexical proxy only.",
                    )
                )

        steps = _ordered_steps(bodies["reproduction_steps"])
        # Empty/punctuation/stop-word-only steps provide no detail. Repeated
        # token sequences cannot increase step count or mean detail.
        distinct_steps = sorted({step for step in steps if step})
        step_detail = (
            math.fsum(min(len(set(step)) / 8, 1.0) for step in distinct_steps) / len(distinct_steps)
            if distinct_steps
            else 0.0
        )
        reproducibility = 0.5 * min(len(distinct_steps) / 3, 1.0) + 0.5 * step_detail
        if not distinct_steps:
            findings.append(
                Finding(
                    code="TEXT_NO_DETAILED_STEPS",
                    severity=Severity.MEDIUM,
                    message="No ordered step with content tokens outside fenced code.",
                )
            )
        if len(distinct_steps) < sum(bool(step) for step in steps):
            findings.append(Finding(code="TEXT_DUPLICATE_STEPS", severity=Severity.LOW))

        prose = "\n".join(_body(section) for section in report.sections)
        lines = [
            tuple(tokens)
            for line in _outside_fences(prose)
            if len(tokens := _content_tokens(_STEP_RE.sub(r"\g<body>", line))) >= 4
        ]
        duplicates = len(lines) - len(set(lines))
        if duplicates:
            findings.append(Finding(code="TEXT_REPEATED_LINES", severity=Severity.LOW))
        findings.append(
            Finding(
                code="TEXT_SEMANTICS_UNASSESSED",
                severity=Severity.INFO,
                message="Lexical features cannot establish claim validity, impact or scope.",
            )
        )
        return EvaluationResult(
            evaluator_name=self.name,
            evaluator_version=self.version,
            case_id=context.case_id,
            decision=Decision.NEEDS_MANUAL_REVIEW,
            confidence=0.5,
            dimensions=DimensionScores(
                reproducibility=round(reproducibility, 6),
                evidence_completeness=round(math.fsum(section_scores.values()) / 7, 6),
                claim_evidence_consistency=0.5,
                impact_calibration=0.5,
                scope_consistency=0.5,
            ),
            findings=findings,
            rationale=(
                "Text-quality control: manual review required. "
                f"{sum(bool(n) for n in unique_tokens.values())}/7 sections have body tokens; "
                f"{len(distinct_steps)} distinct ordered steps. "
                "Semantic dimensions are unassessed; confidence is an uncalibrated constant."
            ),
            metadata={
                "decision_policy": "always_manual_review",
                "confidence_kind": "fixed_uncalibrated_control",
                "unassessed_dimensions": list(_UNASSESSED),
                "section_unique_tokens": unique_tokens,
                "section_content_scores": {k: round(v, 6) for k, v in section_scores.items()},
                "ordered_steps": len(steps),
                "distinct_content_steps": len(distinct_steps),
                "mean_step_detail": round(step_detail, 6),
                "eligible_prose_lines": len(lines),
                "duplicate_prose_lines": duplicates,
                "duplicate_line_ratio": round(duplicates / len(lines), 6) if lines else 0.0,
                "summary_observed_cosine": _cosine(bodies["summary"], bodies["observed_result"]),
            },
        )
