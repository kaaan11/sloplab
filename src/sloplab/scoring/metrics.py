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
    # Per-metric coverage and undefined reasons (E4a): every metric reports
    # its eligible unit counts; unsuitable rows are counted, never silently
    # dropped from a denominator. Entries look like
    # {"eligible": n, "excluded": m, "undefined_reason": str | None}.
    metric_coverage: dict[str, dict[str, object]] = field(default_factory=dict)

    @property
    def canonical_decision_accuracy(self) -> float:
        return self.per_class_accuracy.get("canonical_overall", self.decision_accuracy)


def decision_correct(record: CaseRecord) -> bool:
    return record.expected_decision is not None and record.decision == record.expected_decision


def _record_key(record: CaseRecord) -> tuple[str, str, object]:
    """Singularity key: one row per case, evaluator, and repeat."""
    return (
        record.case_id,
        record.evaluator_name,
        record.evaluation_metadata.get("repeat_index", 0),
    )


def validate_metric_records(records: list[CaseRecord]) -> None:
    """Validate metric inputs at the reader boundary (E4a).

    Raises :class:`ValueError` (never silently drops or repairs) when rows
    are duplicated, when a stored ``correct`` flag disagrees with the
    recomputed decision, when a legacy failed placeholder would be scored,
    or when a mutated row lacks its parent/operator links. Failed and
    not_run outcomes never reach this boundary as records: operational
    failures live in outcome ledgers, and legacy ``failed=True`` markers
    must be converted upstream via ``raise_if_failed_result``.
    """
    seen: set[tuple[str, str, object]] = set()
    for record in records:
        key = _record_key(record)
        if key in seen:
            raise ValueError(f"duplicate metric record for {key}")
        seen.add(key)
        if record.correct != decision_correct(record):
            raise ValueError(
                f"metric record {key} stores correct={record.correct} "
                f"but recomputation gives {decision_correct(record)}"
            )
        if record.evaluation_metadata.get("failed") is True:
            raise ValueError(
                f"metric record {key} is a legacy failed placeholder; "
                "convert it upstream, never score it"
            )
        if record.case_kind == "mutated" and (record.parent_id is None or record.operator is None):
            raise ValueError(f"mutated metric record {key} lacks parent/operator links")


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


def _pair_key(case_id: str, record: CaseRecord) -> tuple[str, str, object]:
    """Bind a parent/child pair within one evaluator repeat."""
    return (
        case_id,
        record.evaluator_name,
        record.evaluation_metadata.get("repeat_index", 0),
    )


def _canonical_decisions(records: list[CaseRecord]) -> dict[tuple[str, str, object], Decision]:
    """Map canonical identity within evaluator/repeat -> decision."""
    return {_pair_key(r.case_id, r): r.decision for r in records if r.case_kind == "canonical"}


def _robustness_pairs(records: list[CaseRecord]) -> tuple[list[bool], int, int]:
    """Drift pairs for quality-neutral mutations + missing + considered counts.

    Returns ``(drifted_flags, missing, considered)`` where each flag compares
    one neutral mutated case against its canonical parent decision. A pair
    resolves only when the parent row is present; missing parents are
    counted, never silently absorbed.
    """
    parents = _canonical_decisions(records)
    drifted: list[bool] = []
    missing = 0
    considered = 0
    for r in records:
        if (
            r.case_kind != "mutated"
            or r.parent_id is None
            or r.expected_decision is None
            or r.expected_decision != _class_default_expected(r)
        ):
            continue
        considered += 1
        parent_decision = parents.get(_pair_key(r.parent_id, r))
        if parent_decision is None:
            missing += 1
            continue
        drifted.append(r.decision != parent_decision)
    return drifted, missing, considered


def compute_robustness_delta(records: list[CaseRecord]) -> float | None:
    """Decision drift under non-degrading mutations.

    For mutated cases whose expected decision equals their class default
    (quality-neutral edits such as professionalization), measures how often the
    evaluator's decision differs from the decision it gave the canonical parent.
    Low drift means stable triage behavior, not proven quality neutrality:
    unchanged decisions must never be read as quality approval.
    """
    drifted, _missing, _considered = _robustness_pairs(records)
    return sum(drifted) / len(drifted) if drifted else None


def _susceptibility_pairs(
    records: list[CaseRecord],
) -> tuple[list[tuple[bool, bool]], int, int]:
    """Paired (child accept, parent accept) flags + missing + considered counts.

    Each eligible presentation-mutated case (expected decision present and
    not accept) pairs with its canonical parent decision. Case-weighted:
    every pair votes once, so parents weigh by child count (descriptive
    contract, explicitly named). Unresolvable pairs (absent parent row, or
    an accept-expected parent outside the baseline definition) are counted,
    never silently absorbed.
    """
    parents = _canonical_decisions(records)
    parent_expected = {
        _pair_key(r.case_id, r): r.expected_decision for r in records if r.case_kind == "canonical"
    }
    pairs: list[tuple[bool, bool]] = []
    missing = 0
    considered = 0
    for r in records:
        if (
            r.operator not in PRESENTATION_OPERATORS
            or r.expected_decision is None
            or r.expected_decision == Decision.ACCEPT
            or r.parent_id is None
        ):
            continue
        considered += 1
        parent_key = _pair_key(r.parent_id, r)
        parent_decision = parents.get(parent_key)
        if parent_decision is None or parent_expected.get(parent_key) == Decision.ACCEPT:
            missing += 1
            continue
        pairs.append((r.decision == Decision.ACCEPT, parent_decision == Decision.ACCEPT))
    return pairs, missing, considered


def compute_presentation_susceptibility(records: list[CaseRecord]) -> float | None:
    """Mean paired acceptance change on presentation-mutated cases (E4a).

    Each eligible child votes its acceptance change against its own
    canonical parent (``child_accept − parent_accept``); the metric is the
    case-weighted mean over pairs. When every pair agrees the result is
    exactly 0 regardless of how children distribute across parents (the old
    unpaired group-rate difference was nonzero there). Restricted to cases
    whose expected decision is NOT accept: susceptibility means
    polished-but-still-broken content gaining acceptance it did not earn.
    """
    pairs, _missing, _considered = _susceptibility_pairs(records)
    if not pairs:
        return None
    return sum(child - parent for child, parent in pairs) / len(pairs)


def _calibration_observations(
    records: list[CaseRecord],
) -> tuple[list[tuple[float, int]], int]:
    """In-range (confidence, correct) observations + out-of-range count.

    Confidences are expected in ``[0, 1]`` (the adapter guarantees the
    range); values outside it are excluded from bins but counted here, never
    silently dropped from the denominator.
    """
    scored: list[tuple[float, int]] = []
    out_of_range = 0
    for r in records:
        raw: object = r.confidence
        if not isinstance(raw, (int, float)):
            out_of_range += 1
            continue
        confidence = float(raw)
        if confidence != confidence or not 0.0 <= confidence <= 1.0:  # NaN or outside
            out_of_range += 1
            continue
        scored.append((confidence, int(decision_correct(r))))
    return scored, out_of_range


def compute_calibration_error(records: list[CaseRecord]) -> float | None:
    """Expected calibration error over equal-width confidence bins.

    Bin boundaries are computed by division (``b / bins``), never multiplication
    (``b * 0.1``): multiplication accumulates IEEE-754 error (e.g. ``6 * 0.1``
    yields 0.6000000000000001), which silently moves boundary confidences such as
    0.6 into the wrong bin. Division is correctly rounded, so a confidence whose
    nearest double equals the literal boundary value lands in its intended bin.
    The final bin is always closed on the right, so confidence 1.0 lands with
    its bin mates instead of vanishing; every in-range record joins exactly
    one bin.
    """
    scored, _out_of_range = _calibration_observations(records)
    if not scored:
        return None
    total_error = 0.0
    for b in range(_CALIBRATION_BINS):
        lo = b / _CALIBRATION_BINS
        hi = (b + 1) / _CALIBRATION_BINS
        if b == _CALIBRATION_BINS - 1:
            members = [(c, ok) for c, ok in scored if lo <= c <= hi]
        else:
            members = [(c, ok) for c, ok in scored if lo <= c < hi]
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

    # Reader boundary: duplicates, correct-flag drift, legacy failed
    # placeholders, and dangling parent/operator links raise here instead of
    # silently skewing a denominator downstream.
    validate_metric_records(records)

    presented = len(records)
    scored = [r for r in records if r.expected_decision is not None]
    bundle.total_cases = len(scored)
    bundle.correct_cases = sum(1 for r in scored if decision_correct(r))
    bundle.decision_accuracy = (
        bundle.correct_cases / bundle.total_cases if bundle.total_cases else 0.0
    )
    bundle.metric_coverage["decision_accuracy"] = {
        "presented": presented,
        "scored": len(scored),
        "unscored_no_expectation": presented - len(scored),
        "undefined_reason": None if scored else "no scored records",
    }

    fr, fr_count = compute_false_reassurance(scored)
    bundle.false_reassurance_rate, bundle.false_reassurance_count = fr, fr_count
    bundle.metric_coverage["false_reassurance"] = {
        "eligible": sum(1 for r in scored if r.expected_decision != Decision.ACCEPT),
        "undefined_reason": None if fr is not None else "no non-accept-expected records",
    }
    orr, orr_count = compute_over_rejection(scored)
    bundle.over_rejection_rate, bundle.over_rejection_count = orr, orr_count
    bundle.metric_coverage["over_rejection"] = {
        "eligible": sum(1 for r in scored if r.expected_decision == Decision.ACCEPT),
        "undefined_reason": None if orr is not None else "no accept-expected records",
    }
    mdr, mdr_total = compute_mutation_detection(scored)
    bundle.mutation_detection_rate, bundle.mutation_detection_total = mdr, mdr_total
    bundle.metric_coverage["mutation_detection"] = {
        "eligible": mdr_total,
        "undefined_reason": None if mdr is not None else "no degrading mutated records",
    }

    bundle.robustness_delta = compute_robustness_delta(scored)
    _drifted, drift_missing, drift_considered = _robustness_pairs(scored)
    bundle.metric_coverage["robustness_delta"] = {
        "pairs": len(_drifted),
        "pairs_missing_parent": drift_missing,
        "considered": drift_considered,
        "undefined_reason": None
        if _drifted
        else "no neutral mutated cases with resolvable parents",
    }
    bundle.presentation_susceptibility = compute_presentation_susceptibility(scored)
    _pairs, pairs_missing, pairs_considered = _susceptibility_pairs(scored)
    bundle.metric_coverage["presentation_susceptibility"] = {
        "pairs": len(_pairs),
        "pairs_unresolved": pairs_missing,
        "children_considered": pairs_considered,
        "undefined_reason": None
        if _pairs
        else "no presentation-mutated cases with resolvable non-accept parents",
    }
    bundle.calibration_error = compute_calibration_error(scored)
    _observations, out_of_range = _calibration_observations(scored)
    bundle.metric_coverage["calibration_error"] = {
        "observations": len(_observations),
        "binned": len(_observations),
        "out_of_range_excluded": out_of_range,
        "undefined_reason": None if _observations else "no in-range observations",
    }
    bundle.dimension_mae = compute_dimension_mae(scored)
    bundle.metric_coverage["dimension_mae"] = {
        "observations": sum(1 for r in scored if (getattr(r, "expected_dimensions", {}) or {})),
        "undefined_reason": None if bundle.dimension_mae else "no expected dimensions",
    }

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
    bundle.metric_coverage["per_class_accuracy"] = {
        "groups": len(bundle.per_class_accuracy),
        "undefined_reason": None if bundle.per_class_accuracy else "no scored records",
    }

    bundle.robustness_score = compute_robustness_score(bundle)
    bundle.metric_coverage["robustness_score"] = {
        "undefined_reason": None if bundle.robustness_score is not None else "no components",
    }
    return bundle
