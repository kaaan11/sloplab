"""Tests for comparative analysis (V25): pairing, taxonomy, bootstrap, stability."""

from __future__ import annotations

import pytest

from sloplab.models.enums import Decision
from sloplab.scoring.comparison import (
    bootstrap_accuracy_ci,
    error_taxonomy,
    paired_win_loss,
    per_class_metrics,
    per_operator_metrics,
    repeat_stability,
)
from tests.unit.test_scoring import record


class TestPairedWinLoss:
    def test_counts_wins_losses_ties(self) -> None:
        a = [
            record("c1"),  # both correct -> tie
            record("c2", decision=Decision.REJECT),  # A wrong
            record("c3", expected=Decision.REJECT, decision=Decision.REJECT),  # A right
        ]
        b = [
            record("c1"),
            record(
                "c2", report_class="invalid", expected=Decision.REJECT, decision=Decision.REJECT
            ),
            record("c3"),
        ]
        comparison = paired_win_loss(a, b)
        assert (comparison.a_wins, comparison.b_wins, comparison.ties) == (0, 1, 2)
        assert comparison.shared_cases == 3

    def test_empty_intersection(self) -> None:
        a = [record("x")]
        b = [record("y")]
        c = paired_win_loss(a, b)
        assert c.shared_cases == 0 and c.a_win_rate == 0.0


class TestBreakdowns:
    def test_per_operator_grouping(self) -> None:
        records = [
            record("p1"),
            record(
                "m1",
                kind="mutated",
                parent_id="p1",
                operator="impact_inflation",
                report_class="valid",
                expected=Decision.NEEDS_MANUAL_REVIEW,
                decision=Decision.NEEDS_MANUAL_REVIEW,
            ),
            record(
                "n1",
                kind="mutated",
                parent_id="p2",
                operator="professionalize_language",
                report_class="valid",
                expected=Decision.ACCEPT,
                decision=Decision.ACCEPT,
            ),
        ]
        groups = per_operator_metrics(records)
        assert set(groups) == {"impact_inflation", "professionalize_language"}
        assert groups["impact_inflation"].total_cases == 1

    def test_per_class_grouping(self) -> None:
        records = [
            record("v", report_class="valid"),
            record("i", report_class="invalid", expected=Decision.REJECT, decision=Decision.ACCEPT),
        ]
        groups = per_class_metrics(records)
        assert groups["invalid"].decision_accuracy == 0.0
        assert groups["valid"].decision_accuracy == 1.0


class TestErrorTaxonomy:
    def test_classification_codes(self) -> None:
        records = [
            record("a", report_class="invalid", expected=Decision.REJECT, decision=Decision.ACCEPT),
            record(
                "b",
                report_class="review",
                expected=Decision.NEEDS_MANUAL_REVIEW,
                decision=Decision.NEEDS_MANUAL_REVIEW,
            ),  # correct, excluded
            record("c", decision=Decision.REJECT),
        ]
        tax = error_taxonomy(records)
        assert tax.total_errors == 2
        assert tax.counts["false_reassurance"] == 1
        assert tax.counts["over_rejection"] == 1


class TestBootstrapCI:
    def test_deterministic_given_seed(self) -> None:
        records = [record(f"r{i}", confidence=0.8) for i in range(30)]
        lo1, pt1, hi1 = bootstrap_accuracy_ci(records, resamples=200, seed=7)
        lo2, pt2, hi2 = bootstrap_accuracy_ci(records, resamples=200, seed=7)
        assert (lo1, pt1, hi1) == (lo2, pt2, hi2)

    def test_perfect_records_give_narrow_high_ci(self) -> None:
        records = [record(f"p{i}") for i in range(50)]
        lo, point, hi = bootstrap_accuracy_ci(records, resamples=300, seed=1)
        assert point == 1.0 and lo > 0.9 and hi == 1.0


class TestRepeatStability:
    def test_unanimity_and_flips(self) -> None:
        r1 = [
            record("a"),
            record(
                "b", decision=Decision.NEEDS_MANUAL_REVIEW, expected=Decision.NEEDS_MANUAL_REVIEW
            ),
        ]
        r2 = [record("a"), record("b")]
        stability = repeat_stability([r1, r2])
        assert stability.cases_compared == 2
        assert stability.unanimous_cases == 1
        assert stability.flipped_cases == 1

    def test_requires_two_runs(self) -> None:
        with pytest.raises(ValueError, match="two repeat"):
            repeat_stability([[record("a")]])
