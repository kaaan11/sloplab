"""Issue #20 out-of-corpus regression tests (PR #33, Wave C contract item 2).

Every boundary sentence below was written from scratch for this test module
(harbor-ferry domain) and MUST NOT occur in ``corpus/``, ``benchmarks/`` or
``experiments/`` (proven by grep; see impl notes). They exercise the same
behaviors as the graphql-028 / wstoken-022 families without copying them:

- conditional marker BEFORE the boundary phrase (leading ``Unless``);
- conditional marker AFTER the boundary phrase (trailing ``if``);
- condition farther than the old 80-char window in the same sentence;
- conditional + unconditional boundary negations in the same report;
- missing boundary support vs explicit contradiction (evidence graph);
- undermining observed result without boundary negation (evidence graph).

These tests are RED on the 0382566 evaluator sources and GREEN at head.
"""

from __future__ import annotations

from typing import Any

from sloplab.corpus.parser import parse_report
from sloplab.evaluators.base import get_evaluator
from sloplab.models.enums import Decision, Severity
from sloplab.models.evaluation import EvaluationContext

SCAFFOLD_HEAD = """\
# HarborLight ferry manifest exposes another vessel's bookings in demo

## Summary

The manifest lookup endpoint returns booking rows that belong to a different
vessel, causing cross-vessel disclosure of demo booking data.

## Affected Component

HarborLight manifest lookup endpoint at https://harbor.example.org.

## Affected Versions

HarborLight 3.1.0 (demo builds only).

## Preconditions

Valid crew account on the demo harbor instance.

## Reproduction Steps

1. Sign in as dispatcher for ferry Bluefin.
2. Send `GET /manifests/77` scoped to ferry Kestrel.
3. Observe the response body.

## Observed Result

BOOKING_SENTENCE

## Expected Security Boundary

BOUNDARY_SENTENCE

## Impact

Medium confidentiality impact on demo manifest data only.
"""

NEUTRAL_OBSERVED = "Booking rows for ferry Kestrel are returned to the Bluefin dispatcher session."
NEUTRAL_BOUNDARY = "Cross-vessel manifest reads must require dispatcher-scoped authorization."


def _body(*, observed: str = NEUTRAL_OBSERVED, boundary: str = NEUTRAL_BOUNDARY) -> str:
    return SCAFFOLD_HEAD.replace("BOOKING_SENTENCE", observed).replace(
        "BOUNDARY_SENTENCE", boundary
    )


def _body_without_boundary() -> str:
    text = _body()
    start = text.index("## Expected Security Boundary")
    end = text.index("## Impact")
    return text[:start] + text[end:]


def _evaluate(text: str, evaluator: str, case_id: str) -> Any:
    doc = parse_report(text, fixture_id=case_id, path="x")
    evaluator_obj = get_evaluator(evaluator)
    ctx = EvaluationContext(report=doc, case_id=case_id, labels={})
    return evaluator_obj.evaluate(doc, ctx)


def _rules(text: str, case_id: str) -> Any:
    return _evaluate(text, "rules-baseline", case_id)


def _graph(text: str, case_id: str) -> Any:
    return _evaluate(text, "evidence-graph-baseline", case_id)


class TestOutOfCorpusRulesBoundary:
    def test_out_of_corpus_leading_marker_before_negation(self) -> None:
        text = _body(
            boundary=(
                "Unless the depot master switch on the north pier stays locked "
                "to single-vessel mode during night sailings, no security "
                "boundary between vessels is crossed."
            )
        )
        result = _rules(text, "ooc-001")
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW
        codes = {f.code for f in result.findings}
        assert "CONDITIONAL_BOUNDARY_STATEMENT" in codes
        assert "NO_SECURITY_BOUNDARY_STATED" not in codes

    def test_out_of_corpus_trailing_marker_after_negation(self) -> None:
        text = _body(
            boundary=(
                "No security boundary between vessels is crossed "
                "if the query stays inside one vessel."
            )
        )
        result = _rules(text, "ooc-002")
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW
        codes = {f.code for f in result.findings}
        assert "CONDITIONAL_BOUNDARY_STATEMENT" in codes
        assert "NO_SECURITY_BOUNDARY_STATED" not in codes

    def test_out_of_corpus_far_condition_beyond_old_window(self) -> None:
        text = _body(
            boundary=(
                "When the overnight festival schedule plus all standby crew "
                "rosters posted at the north pier office remain exactly as "
                "published for the whole regatta week, no security boundary "
                "between vessels is crossed."
            )
        )
        result = _rules(text, "ooc-003")
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW
        codes = {f.code for f in result.findings}
        assert "CONDITIONAL_BOUNDARY_STATEMENT" in codes
        assert "NO_SECURITY_BOUNDARY_STATED" not in codes

    def test_out_of_corpus_conditional_does_not_mask_unconditional(self) -> None:
        text = _body(
            boundary=(
                "Unless the night roster is active, no security boundary "
                "between depot vessels is crossed. There is no security "
                "boundary between the Bluefin and Kestrel dispatch queues."
            )
        )
        result = _rules(text, "ooc-004")
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "CONDITIONAL_BOUNDARY_STATEMENT" in codes
        assert "NO_SECURITY_BOUNDARY_STATED" in codes


class TestOutOfCorpusEvidenceGraph:
    def test_out_of_corpus_missing_boundary_is_missing_support(self) -> None:
        result = _graph(_body_without_boundary(), "ooc-005")
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW
        codes = {f.code for f in result.findings}
        assert "GRAPH_MISSING_BOUNDARY_SUPPORT" in codes
        assert "GRAPH_BOUNDARY_CONTRADICTS_CLAIM" not in codes
        assert "BOUNDARY_NEGATED_BY_AUTHOR" not in codes

    def test_out_of_corpus_explicit_contradiction_is_high_severity(self) -> None:
        text = _body(
            boundary=(
                "No security boundary applies to manifest reads; dispatch "
                "scoping is a display preference."
            )
        )
        result = _graph(text, "ooc-006")
        assert result.decision == Decision.REJECT
        by_code = {f.code: f for f in result.findings}
        assert "GRAPH_BOUNDARY_CONTRADICTS_CLAIM" in by_code
        assert by_code["GRAPH_BOUNDARY_CONTRADICTS_CLAIM"].severity == Severity.HIGH
        assert "BOUNDARY_NEGATED_BY_AUTHOR" in by_code
        assert "GRAPH_MISSING_BOUNDARY_SUPPORT" not in by_code

    def test_out_of_corpus_undermining_observed_is_not_author_negation(self) -> None:
        text = _body(
            observed=("However, repeated harbor checks returned 403 and no vessel rows came back.")
        )
        result = _graph(text, "ooc-007")
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "GRAPH_OBSERVED_UNDERMINES_CLAIM" in codes
        assert "BOUNDARY_NEGATED_BY_AUTHOR" not in codes


class TestNegativeControlsUnconditional:
    def test_neutral_scaffold_is_accepted(self) -> None:
        result = _rules(_body(), "neg-000")
        assert result.decision == Decision.ACCEPT

    def test_unconditional_negation_still_rejects(self) -> None:
        text = _body(boundary="No security boundary applies to this manifest report.")
        result = _rules(text, "neg-001")
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "NO_SECURITY_BOUNDARY_STATED" in codes

    def test_marker_in_unrelated_sentence_does_not_force_review(self) -> None:
        text = _body(
            boundary=(
                "No security boundary applies to this manifest report. "
                "Write to the harbor office if sailing times look wrong."
            )
        )
        result = _rules(text, "neg-002")
        assert result.decision == Decision.REJECT
        codes = {f.code for f in result.findings}
        assert "NO_SECURITY_BOUNDARY_STATED" in codes
        assert "CONDITIONAL_BOUNDARY_STATEMENT" not in codes
