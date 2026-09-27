"""Comparative analysis across evaluators (V0.2).

All randomness is seeded, so every analysis output is byte-reproducible for a
fixed input set + base seed.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
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


def _repeat_index(record: CaseRecord) -> object:
    """Repeat identity from the existing ``evaluation_metadata`` field.

    ``seed`` is the corpus sampling seed (identical across repeats) and must
    NOT be used as a repeat tag. The established repeat tag is
    ``evaluation_metadata["repeat_index"]`` (written by the pilot, read by
    the metrics singularity keys), defaulting to 0 for single-repeat
    deterministic records. No new schema field is required.
    """
    meta = record.evaluation_metadata or {}
    tag = meta.get("repeat_index", 0)
    return 0 if tag is None else tag


def _paired_correctness(records: list[CaseRecord]) -> dict[tuple[str, object], bool]:
    """Map (case_id, repeat) -> correctness, failing loudly on ambiguity.

    A repeated ``case_id`` without a distinguishing repeat identity (or the
    same ``(case_id, repeat)`` twice) raises ``ValueError`` naming the case
    instead of letting input order silently pick the survivor.
    """
    keyed: dict[tuple[str, object], bool] = {}
    for r in records:
        key = (r.case_id, _repeat_index(r))
        if key in keyed:
            raise ValueError(
                f"paired_win_loss: duplicate records for case_id={r.case_id!r} "
                f"repeat={key[1]!r}; tag repeats via "
                "evaluation_metadata['repeat_index']"
            )
        keyed[key] = r.correct
    return keyed


def paired_win_loss(records_a: list[CaseRecord], records_b: list[CaseRecord]) -> PairedComparison:
    """Case-level correctness pairing between two evaluators on shared cases.

    Pairing is over ``(case_id, repeat)`` when repeat identity is present,
    otherwise over ``case_id`` (single-repeat records all read as repeat 0,
    matching the metrics singularity keys). Shared keys are compared in
    sorted order, so reversed inputs give identical results.
    """
    by_case_a = _paired_correctness(records_a)
    by_case_b = _paired_correctness(records_b)
    shared = sorted(set(by_case_a) & set(by_case_b), key=repr)

    comparison = PairedComparison(
        evaluator_a=records_a[0].evaluator_name if records_a else "A",
        evaluator_b=records_b[0].evaluator_name if records_b else "B",
        shared_cases=len(shared),
    )
    for key in shared:
        a_ok, b_ok = by_case_a[key], by_case_b[key]
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
# Cluster bootstrap (issue #48, binding implementation contract)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClusterBootstrap:
    """Cluster-resampled accuracy intervals plus the paired evaluator diff.

    Attributes mirror the document layout in ``analysis.json``: per-evaluator
    LOW/HIGH percentile pairs, the paired difference (percentile pair plus
    point) computed on the SAME resamples, and provenance counts.
    """

    clusters: int
    resamples: int
    seed: int
    accuracy: dict[str, tuple[float, float]]
    paired_difference: dict[str, tuple[float, float, float]] | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "clusters": self.clusters,
            "resamples": self.resamples,
            "seed": self.seed,
            "accuracy": {name: list(value) for name, value in self.accuracy.items()},
            "paired_difference": (
                {name: list(value) for name, value in self.paired_difference.items()}
                if self.paired_difference is not None
                else None
            ),
        }


def _pair_ids_from_root(corpus_root: Path | None) -> dict[str, str]:
    """Build canonical case_id -> pair_id map from manifests under corpus_root.

    Uses the corpus loader only; a missing or unreadable corpus degrades to an
    empty map (clusters then keep their case_id keys, visible via the cluster
    count). Imports stay function-local so call-time patching of the corpus
    loader (as regression tests do) keeps working.
    """
    from sloplab.corpus.loader import FixtureError, discover_fixtures

    pairs: dict[str, str] = {}
    if corpus_root is None:
        return pairs
    try:
        canonical, _derived = discover_fixtures(corpus_root)
    except (FixtureError, OSError):
        return pairs
    for fixture in canonical:
        if fixture.manifest.pair_id is not None:
            pairs[fixture.manifest.id] = fixture.manifest.pair_id
    return pairs


def cluster_bootstrap_accuracy_ci(
    records: list[CaseRecord],
    *,
    resamples: int = 2000,
    ci: float = 0.95,
    seed: int = 0,
    pair_ids: dict[str, str] | None = None,
) -> ClusterBootstrap:
    """Logical-report-cluster bootstrap CI (issue #48 binding contract).

    Cluster key: ``parent_id`` for derived cases, ``case_id`` for canonical
    cases; when the canonical manifest of that id carries a ``pair_id``, the
    cluster is keyed by ``pair_id`` instead (the presentation pair is one
    logical report; the pair mapping is resolved through the parent for
    derived rows too, merging 60 canonical fixtures into 52 clusters). Cluster
    order is first appearance in ``records``. ``random.Random(seed)`` draws
    ``len(order)`` clusters per resample with ``rng.choice``;
    accuracy = correct cases / cases in the drawn clusters; percentile
    indices are ``int(0.025 * n)`` and ``int(0.975 * n)`` on the sorted list
    (for 2000 resamples at 95%: values 50 and 1950). The paired difference
    between the first two evaluators (sorted by name) is computed on the SAME
    resample draws; with fewer than two evaluators it is ``None``.
    """
    if not records:
        return ClusterBootstrap(
            clusters=0, resamples=resamples, seed=seed, accuracy={}, paired_difference=None
        )
    pairs = pair_ids or {}
    keys = [
        pairs.get(r.case_id, r.case_id)
        if r.case_kind == "canonical"
        else pairs.get(r.parent_id or "", r.parent_id or r.case_id)
        for r in records
    ]
    seen: dict[str, int] = {}
    order: list[str] = []
    for key in keys:
        if key not in seen:
            seen[key] = 1
            order.append(key)
    # Per evaluator: cluster -> [correct, cases] tallies.
    tables: dict[str, dict[str, list[int]]] = {}
    for record, key in zip(records, keys, strict=True):
        table = tables.setdefault(record.evaluator_name, {})
        tally: list[int] = table.setdefault(key, [0, 0])
        tally[0] += 1 if record.correct else 0
        tally[1] += 1

    rng = random.Random(seed)
    acc_values: dict[str, list[float]] = {name: [] for name in tables}
    diff_values: list[float] = []
    names = sorted(tables)
    for _ in range(resamples):
        draws = [rng.choice(order) for _ in range(len(order))]
        accs: dict[str, float] = {}
        for name in names:
            table = tables[name]
            correct = cases = 0
            for key in draws:
                drawn: list[int] | None = table.get(key)
                if drawn is not None:
                    correct += drawn[0]
                    cases += drawn[1]
            accs[name] = correct / cases if cases else 0.0
            acc_values[name].append(accs[name])
        if len(names) >= 2:
            diff_values.append(accs[names[1]] - accs[names[0]])

    def percentile(values: list[float]) -> tuple[float, float]:
        ordered = sorted(values)
        size = len(ordered)
        return ordered[int((1.0 - ci) / 2 * size)], ordered[int((1.0 - (1.0 - ci) / 2) * size)]

    accuracy = {name: percentile(acc_values[name]) for name in names}
    paired: dict[str, tuple[float, float, float]] | None = None
    if len(names) >= 2:
        point = sum(diff_values) / len(diff_values) if diff_values else 0.0
        paired = {f"{names[0]} - {names[1]}": percentile(diff_values) + (point,)}
    return ClusterBootstrap(
        clusters=len(order),
        resamples=resamples,
        seed=seed,
        accuracy=accuracy,
        paired_difference=paired,
    )


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
    incomplete_cases: int = 0
    incomplete_case_ids: list[str] = field(default_factory=list)

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
    """Agreement across >=2 repeat runs of a stochastic evaluator.

    A case counts as unanimous/flipped only when it is present in EVERY
    repeat run. Cases missing from any repeat are reported separately via
    ``incomplete_cases`` / ``incomplete_case_ids`` and never as unanimous.
    Operational failures never reach this boundary as records: they live in
    the pilot outcome ledger, which withholds stability on incomplete
    coverage. The serialized ``as_dict()`` keys are unchanged, so
    full-coverage single-observation output is byte-identical to before.
    """
    if len(repeat_sets) < 2:
        raise ValueError("repeat_stability requires at least two repeat runs")
    by_case: dict[str, list[tuple[int, CaseRecord]]] = defaultdict(list)
    for repeat_index, records in enumerate(repeat_sets):
        for r in records:
            by_case[r.case_id].append((repeat_index, r))

    total_repeats = len(repeat_sets)
    stability = RepeatStability(repeats=total_repeats, cases_compared=len(by_case))
    spreads: list[float] = []
    incomplete: list[str] = []
    for case_id in sorted(by_case):
        entries = by_case[case_id]
        if len({repeat_index for repeat_index, _ in entries}) < total_repeats:
            incomplete.append(case_id)
            continue
        decisions = {e.decision for _, e in entries}
        confs = [e.confidence for _, e in entries]
        if len(decisions) == 1:
            stability.unanimous_cases += 1
        else:
            stability.flipped_cases += 1
        if len(confs) > 1:
            spreads.append(max(confs) - min(confs))
    stability.incomplete_cases = len(incomplete)
    stability.incomplete_case_ids = incomplete
    stability.mean_confidence_spread = sum(spreads) / len(spreads) if spreads else 0.0
    return stability
