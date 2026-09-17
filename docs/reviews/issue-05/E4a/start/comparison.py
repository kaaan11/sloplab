"""Comparative analysis across evaluators (V0.2).

All randomness is seeded, so every analysis output is byte-reproducible for a
fixed input set + base seed.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sloplab.models.run import CaseRecord
from sloplab.scoring.metrics import MetricBundle, compute_metrics

# ---------------------------------------------------------------------------
# Paired win/loss comparison
# ---------------------------------------------------------------------------


@dataclass
class PairedComparison:
    evaluator_a: str
    evaluator_b: str
    shared_cases: int
    a_wins: int = 0
    b_wins: int = 0
    ties: int = 0

    @property
    def a_win_rate(self) -> float:
        decided = self.a_wins + self.b_wins
        return self.a_wins / decided if decided else 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "evaluator_a": self.evaluator_a,
            "evaluator_b": self.evaluator_b,
            "shared_cases": self.shared_cases,
            "a_wins": self.a_wins,
            "b_wins": self.b_wins,
            "ties": self.ties,
            "a_win_rate": round(self.a_win_rate, 4),
        }


def paired_win_loss(records_a: list[CaseRecord], records_b: list[CaseRecord]) -> PairedComparison:
    """Case-level correctness pairing between two evaluators on shared cases."""
    by_case_a = {r.case_id: r.correct for r in records_a}
    by_case_b = {r.case_id: r.correct for r in records_b}
    shared = sorted(set(by_case_a) & set(by_case_b))

    comparison = PairedComparison(
        evaluator_a=records_a[0].evaluator_name if records_a else "A",
        evaluator_b=records_b[0].evaluator_name if records_b else "B",
        shared_cases=len(shared),
    )
    for case_id in shared:
        a_ok, b_ok = by_case_a[case_id], by_case_b[case_id]
        if a_ok and not b_ok:
            comparison.a_wins += 1
        elif b_ok and not a_ok:
            comparison.b_wins += 1
        else:
            comparison.ties += 1
    return comparison


# ---------------------------------------------------------------------------
# Grouped metric breakdowns
# ---------------------------------------------------------------------------


def group_by(records: list[CaseRecord], key_fn: Any) -> dict[str, list[CaseRecord]]:
    groups: dict[str, list[CaseRecord]] = defaultdict(list)
    for record in records:
        key = key_fn(record)
        if key is None:
            continue
        groups[key].append(record)
    return dict(groups)


def per_operator_metrics(records: list[CaseRecord]) -> dict[str, MetricBundle]:
    groups = group_by(records, lambda r: r.operator)
    return {
        op: compute_metrics(rs, f"{rs[0].evaluator_name}:{op}") for op, rs in sorted(groups.items())
    }


def per_class_metrics(records: list[CaseRecord]) -> dict[str, MetricBundle]:
    groups = group_by(records, lambda r: r.report_class)
    return {
        cls: compute_metrics(rs, f"{rs[0].evaluator_name}:{cls}")
        for cls, rs in sorted(groups.items())
    }


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------

ERROR_TAXONOMY_CODES: dict[tuple[str, str], str] = {
    # (expected, actual)
    ("accept", "reject"): "over_rejection",
    ("accept", "needs_manual_review"): "premature_deferral",
    ("reject", "accept"): "false_reassurance",
    ("reject", "needs_manual_review"): "deferred_invalid",
    ("needs_manual_review", "accept"): "premature_accept",
    ("needs_manual_review", "reject"): "over_strict_reject",
}


@dataclass
class ErrorTaxonomy:
    evaluator_name: str
    total_errors: int = 0
    counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "evaluator_name": self.evaluator_name,
            "total_errors": self.total_errors,
            "counts": dict(sorted(self.counts.items())),
        }


def error_taxonomy(records: list[CaseRecord]) -> ErrorTaxonomy:
    """Classify each incorrect case into a named error type."""
    name = records[0].evaluator_name if records else "unknown"
    taxonomy = ErrorTaxonomy(evaluator_name=name)
    for r in records:
        if r.correct or r.expected_decision is None:
            continue
        code = ERROR_TAXONOMY_CODES.get(
            (r.expected_decision.value, r.decision.value), "other_misclassification"
        )
        taxonomy.counts[code] = taxonomy.counts.get(code, 0) + 1
        taxonomy.total_errors += 1
    return taxonomy


def taxonomy_by_group(records: list[CaseRecord], key_fn: Any) -> dict[str, dict[str, int]]:
    """Error-type counts grouped by an arbitrary key (operator, class, ...)."""
    out: dict[str, dict[str, int]] = {}
    for key, group in sorted(group_by(records, key_fn).items()):
        tax = error_taxonomy(group)
        out[key] = tax.counts
    return out


# ---------------------------------------------------------------------------
# Bootstrap confidence intervals (seeded -> reproducible)
# ---------------------------------------------------------------------------


def bootstrap_accuracy_ci(
    records: list[CaseRecord],
    *,
    resamples: int = 2000,
    ci: float = 0.95,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Percentile bootstrap CI for decision accuracy. Deterministic given seed."""
    if not records:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    n = len(records)
    values: list[float] = []
    for _ in range(resamples):
        sample_correct = sum(1 for _ in range(n) if records[rng.randrange(n)].correct)
        values.append(sample_correct / n)
    values.sort()
    alpha = (1.0 - ci) / 2
    lo_idx = int(alpha * resamples)
    hi_idx = min(int((1 - alpha) * resamples), resamples - 1)
    point = sum(1 for r in records if r.correct) / n
    return values[lo_idx], point, values[hi_idx]


# ---------------------------------------------------------------------------
# Repeat stability / agreement (stochastic evaluators, e.g. LLM repeats)
# ---------------------------------------------------------------------------


@dataclass
class RepeatStability:
    repeats: int
    cases_compared: int
    unanimous_cases: int = 0
    flipped_cases: int = 0
    mean_confidence_spread: float = 0.0

    @property
    def unanimity_rate(self) -> float:
        return self.unanimous_cases / self.cases_compared if self.cases_compared else 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "repeats": self.repeats,
            "cases_compared": self.cases_compared,
            "unanimous_cases": self.unanimous_cases,
            "flipped_cases": self.flipped_cases,
            "mean_confidence_spread": round(self.mean_confidence_spread, 4),
            "unanimity_rate": round(self.unanimity_rate, 4),
        }


def repeat_stability(repeat_sets: list[list[CaseRecord]]) -> RepeatStability:
    """Agreement across >=2 repeat runs of a stochastic evaluator."""
    if len(repeat_sets) < 2:
        raise ValueError("repeat_stability requires at least two repeat runs")
    by_case: dict[str, list[CaseRecord]] = defaultdict(list)
    for records in repeat_sets:
        for r in records:
            by_case[r.case_id].append(r)

    stability = RepeatStability(repeats=len(repeat_sets), cases_compared=len(by_case))
    spreads: list[float] = []
    for _case_id in sorted(by_case):
        entries = by_case[_case_id]
        decisions = {e.decision for e in entries}
        confs = [e.confidence for e in entries]
        if len(decisions) == 1:
            stability.unanimous_cases += 1
        else:
            stability.flipped_cases += 1
        if len(confs) > 1:
            spreads.append(max(confs) - min(confs))
    stability.mean_confidence_spread = sum(spreads) / len(spreads) if spreads else 0.0
    return stability
