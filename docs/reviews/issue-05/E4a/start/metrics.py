"""Metric computation over evaluated case records.

All definitions are documented in docs/methodology.md. Metrics never look at report
text - they operate purely on CaseRecord data.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from sloplab.models.enums import DIMENSIONS, Decision, ReportClass, canonical_expected_decision
from sloplab.models.run import CaseRecord

PRESENTATION_OPERATORS = frozenset({"professionalize_language", "confidence_overstatement"})
_CALIBRATION_BINS = 10


@dataclass
class ClassMetrics:
    total: int = 0
    correct: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass
class MetricBundle:
    evaluator_name: str
    total_cases: int = 0
    correct_cases: int = 0
    decision_accuracy: float = 0.0
    false_reassurance_rate: float | None = None
    false_reassurance_count: int = 0
    over_rejection_rate: float | None = None
    over_rejection_count: int = 0
    mutation_detection_rate: float | None = None
    mutation_detection_total: int = 0
    robustness_delta: float | None = None
    presentation_susceptibility: float | None = None
    calibration_error: float | None = None
    dimension_mae: dict[str, float] = field(default_factory=dict)
    per_class_accuracy: dict[str, float] = field(default_factory=dict)
    robustness_score: float | None = None  # auxiliary weighted summary

    @property
    def canonical_decision_accuracy(self) -> float:
        return self.per_class_accuracy.get("canonical_overall", self.decision_accuracy)


def decision_correct(record: CaseRecord) -> bool:
    return record.expected_decision is not None and record.decision == record.expected_decision


def _class_default_expected(record: CaseRecord) -> Decision:
    return canonical_expected_decision(ReportClass(record.report_class))


def compute_false_reassurance(records: list[CaseRecord]) -> tuple[float | None, int]:
    """Fraction of non-accept-expected cases the evaluator accepted."""
    eligible = [r for r in records if r.expected_decision != Decision.ACCEPT]
    if not eligible:
        return None, 0
    reassured = sum(1 for r in eligible if r.decision == Decision.ACCEPT)
    return reassured / len(eligible), reassured


def compute_over_rejection(records: list[CaseRecord]) -> tuple[float | None, int]:
    """Fraction of accept-expected (valid) cases the evaluator rejected."""
    eligible = [r for r in records if r.expected_decision == Decision.ACCEPT]
    if not eligible:
        return None, 0
    rejected = sum(1 for r in eligible if r.decision == Decision.REJECT)
    return rejected / len(eligible), rejected


def compute_mutation_detection(records: list[CaseRecord]) -> tuple[float | None, int]:
    """Detection of degrading mutations: mutated cases whose expected decision differs
    from their class default. Detected means the evaluator matched the expectation."""
    eligible = [
        r
        for r in records
        if r.case_kind == "mutated"
        and r.expected_decision is not None
        and r.operator is not None
        and r.expected_decision != _class_default_expected(r)
    ]
    if not eligible:
        return None, 0
    detected = sum(1 for r in eligible if decision_correct(r))
    return detected / len(eligible), len(eligible)


def compute_robustness_delta(records: list[CaseRecord]) -> float | None:
    """Decision drift under non-degrading mutations.

    For mutated cases whose expected decision equals their class default
    (quality-neutral edits such as professionalization), measures how often the
    evaluator's decision differs from the decision it gave the canonical parent.
    Low is good: triage behavior should not wobble when substance is unchanged.
    """
    decisions_by_case: dict[str, Decision] = {r.case_id: r.decision for r in records}

    comparisons = 0
    drifted = 0
    for r in records:
        if (
            r.case_kind != "mutated"
            or r.parent_id is None
            or r.expected_decision is None
            or r.expected_decision != _class_default_expected(r)
        ):
            continue
        parent_decision = decisions_by_case.get(r.parent_id)
        if parent_decision is None:
            continue
        comparisons += 1
        drifted += int(r.decision != parent_decision)
    return drifted / comparisons if comparisons else None


def compute_presentation_susceptibility(records: list[CaseRecord]) -> float | None:
    """Acceptance-rate increase on presentation-mutated cases vs their canonical parents.

    Restricted to cases whose expected decision is NOT accept: susceptibility means
    polished-but-still-broken content gaining acceptance it did not earn.
    """
    pres_cases = [
        r
        for r in records
        if r.operator in PRESENTATION_OPERATORS
        and r.expected_decision is not None
        and r.expected_decision != Decision.ACCEPT
    ]
    if not pres_cases:
        return None
    parent_ids = {r.parent_id for r in pres_cases if r.parent_id}
    canon_accepts = [
        r
        for r in records
        if r.case_kind == "canonical"
        and r.case_id in parent_ids
        and r.expected_decision is not None
        and r.expected_decision != Decision.ACCEPT
    ]
    if not canon_accepts:
        return None
    baseline = sum(1 for r in canon_accepts if r.decision == Decision.ACCEPT) / len(canon_accepts)
    mutated = sum(1 for r in pres_cases if r.decision == Decision.ACCEPT) / len(pres_cases)
    return mutated - baseline


def compute_calibration_error(records: list[CaseRecord]) -> float | None:
    """Expected calibration error over equal-width confidence bins.

    Bin boundaries are computed by division (``b / bins``), never multiplication
    (``b * 0.1``): multiplication accumulates IEEE-754 error (e.g. ``6 * 0.1``
    yields 0.6000000000000001), which silently moves boundary confidences such as
    0.6 into the wrong bin. Division is correctly rounded, so a confidence whose
    nearest double equals the literal boundary value lands in its intended bin.
    The final bin is closed on the right so confidence 1.0 is always captured.
    """
    scored = [(r.confidence, int(decision_correct(r))) for r in records]
    if not scored:
        return None
    total_error = 0.0
    for b in range(_CALIBRATION_BINS):
        lo = b / _CALIBRATION_BINS
        hi = (b + 1) / _CALIBRATION_BINS
        members = [(c, ok) for c, ok in scored if lo <= c < hi]
        if b == _CALIBRATION_BINS - 1 and not members:
            members = [(c, ok) for c, ok in scored if lo <= c <= hi]
        if not members:
            continue
        avg_conf = sum(c for c, _ in members) / len(members)
        avg_acc = sum(ok for _, ok in members) / len(members)
        total_error += len(members) / len(scored) * abs(avg_conf - avg_acc)
    return total_error


def compute_dimension_mae(records: list[CaseRecord]) -> dict[str, float]:
    """Mean absolute error per dimension where expected dimensions exist."""
    sums: dict[str, list[float]] = defaultdict(list)
    for r in records:
        expected = getattr(r, "expected_dimensions", {}) or {}
        if not expected:
            continue
        for dim in DIMENSIONS:
            if dim in expected and dim in r.dimensions:
                sums[dim].append(abs(r.dimensions[dim] - expected[dim]))
    return {dim: round(sum(v) / len(v), 4) for dim, v in sorted(sums.items())}


def compute_robustness_score(bundle: MetricBundle) -> float | None:
    """Auxiliary weighted summary; primary results are per-dimension metrics.

    40% mutation detection + 25% low false reassurance + 15% canonical accuracy
    + 10% calibration + 10% presentation robustness.
    """
    parts: list[tuple[float, float]] = []
    if bundle.mutation_detection_rate is not None:
        parts.append((0.40, bundle.mutation_detection_rate))
    if bundle.false_reassurance_rate is not None:
        parts.append((0.25, 1.0 - bundle.false_reassurance_rate))
    if bundle.total_cases:
        parts.append((0.15, bundle.decision_accuracy))
    if bundle.calibration_error is not None:
        parts.append((0.10, 1.0 - bundle.calibration_error))
    if bundle.presentation_susceptibility is not None:
        parts.append((0.10, 1.0 - max(0.0, bundle.presentation_susceptibility)))
    if not parts:
        return None
    weight_sum = sum(w for w, _ in parts)
    return round(sum(w * v for w, v in parts) / weight_sum, 4)


def compute_metrics(records: list[CaseRecord], evaluator_name: str = "") -> MetricBundle:
    name = evaluator_name or (records[0].evaluator_name if records else "unknown")
    bundle = MetricBundle(evaluator_name=name)

    scored = [r for r in records if r.expected_decision is not None]
    bundle.total_cases = len(scored)
    bundle.correct_cases = sum(1 for r in scored if decision_correct(r))
    bundle.decision_accuracy = (
        bundle.correct_cases / bundle.total_cases if bundle.total_cases else 0.0
    )

    fr, fr_count = compute_false_reassurance(scored)
    bundle.false_reassurance_rate, bundle.false_reassurance_count = fr, fr_count
    orr, orr_count = compute_over_rejection(scored)
    bundle.over_rejection_rate, bundle.over_rejection_count = orr, orr_count
    mdr, mdr_total = compute_mutation_detection(scored)
    bundle.mutation_detection_rate, bundle.mutation_detection_total = mdr, mdr_total

    bundle.robustness_delta = compute_robustness_delta(scored)
    bundle.presentation_susceptibility = compute_presentation_susceptibility(scored)
    bundle.calibration_error = compute_calibration_error(scored)
    bundle.dimension_mae = compute_dimension_mae(scored)

    by_class: dict[str, ClassMetrics] = defaultdict(ClassMetrics)
    canonical_acc: dict[str, list[int]] = defaultdict(list)
    for r in scored:
        by_class[r.report_class].total += 1
        by_class[r.report_class].correct += int(decision_correct(r))
        if r.case_kind == "canonical":
            canonical_acc["canonical_overall"].append(int(decision_correct(r)))
    bundle.per_class_accuracy = {cls: m.accuracy for cls, m in sorted(by_class.items())}
    if canonical_acc.get("canonical_overall"):
        vals = canonical_acc["canonical_overall"]
        bundle.per_class_accuracy["canonical_overall"] = sum(vals) / len(vals)

    bundle.robustness_score = compute_robustness_score(bundle)
    return bundle
