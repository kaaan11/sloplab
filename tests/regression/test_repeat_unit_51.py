"""Issue #51 (R1-008): paired_win_loss and repeat_stability keep the repeat unit.

Contract (binding "Uygulama sözlesmesi" comment):
- paired_win_loss: a repeated case_id without repeat identity raises an
  explicit ValueError naming the case; with repeat identity the pairing key
  is (case_id, repeat). Same records in reversed order give the same result
  or the same error.
- repeat_stability: unanimous requires the case in EVERY repeat; cases
  missing from any repeat are reported via incomplete_cases /
  incomplete_case_ids, never as unanimous.
- Full-coverage single-observation output is byte-identical to base behavior.
"""

from __future__ import annotations

from typing import Any

import pytest

from sloplab.models.enums import Decision
from sloplab.models.run import CaseRecord
from sloplab.scoring.comparison import paired_win_loss, repeat_stability
from tests.unit.test_scoring import record


def _repeat(case_id: str, repeat_index: int, **kwargs: Any) -> CaseRecord:
    """Build a record carrying the existing repeat identity field."""
    rec = record(case_id, **kwargs)
    rec.evaluation_metadata["repeat_index"] = repeat_index
    return rec


class TestPairedWinLossRepeatUnit:
    def test_reversed_duplicates_raise_same_error(self) -> None:
        ok = record("dup-case")
        wrong = record("dup-case", decision=Decision.REJECT)
        peer = [record("dup-case")]
        with pytest.raises(ValueError, match="dup-case"):
            paired_win_loss([ok, wrong], peer)
        with pytest.raises(ValueError, match="dup-case"):
            paired_win_loss([wrong, ok], peer)

    def test_tagged_repeats_pair_order_independently(self) -> None:
        ana = [_repeat("c1", 0), _repeat("c1", 1, decision=Decision.REJECT)]
        bnb = [_repeat("c1", 0), _repeat("c1", 1)]
        first = paired_win_loss(ana, bnb)
        second = paired_win_loss(list(reversed(ana)), bnb)
        assert first.as_dict() == second.as_dict()
        assert (first.a_wins, first.b_wins, first.ties) == (0, 1, 1)
        assert first.shared_cases == 2


class TestRepeatStabilityCoverage:
    def test_partial_repeat_is_incomplete_not_unanimous(self) -> None:
        stability = repeat_stability([[record("solo-case")], [], []])
        assert stability.cases_compared == 1
        assert stability.unanimous_cases == 0
        assert stability.flipped_cases == 0
        assert stability.incomplete_cases == 1
        assert stability.incomplete_case_ids == ["solo-case"]

    def test_full_coverage_output_byte_identical_to_base(self) -> None:
        run_a = [
            record("a"),
            record(
                "b",
                decision=Decision.NEEDS_MANUAL_REVIEW,
                expected=Decision.NEEDS_MANUAL_REVIEW,
            ),
        ]
        run_b = [record("a"), record("b")]
        stability = repeat_stability([run_a, run_b])
        assert stability.as_dict() == {
            "repeats": 2,
            "cases_compared": 2,
            "unanimous_cases": 1,
            "flipped_cases": 1,
            "mean_confidence_spread": 0.0,
            "unanimity_rate": 0.5,
        }
        assert stability.incomplete_cases == 0
        assert stability.incomplete_case_ids == []
