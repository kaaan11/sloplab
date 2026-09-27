"""Issue #48 reference test: cluster bootstrap on the frozen 0382566 records.

Binding implementation contract (2026-09-27 comment, overriding the issue body):
cluster bootstrap + paired difference ONLY (MDR/FAR/ECE intervals are out of
scope). The contract pins, on the 0382566 records, rounded to 4 decimals:

- rules-baseline accuracy CI      [0.7297, 0.8771]
- evidence-graph-baseline CI      [0.4581, 0.6300]
- paired difference rules - graph [0.1679, 0.3547]

with 52 clusters, first-appearance order, ``random.Random(20260825)``,
2000 resamples of 52 ``rng.choice`` draws, accuracy = correct / cases in the
drawn clusters, and percentile indices ``v[int(0.025 * n)]`` / ``v[int(0.975 * n)]``.
"""

from __future__ import annotations

import json
from pathlib import Path

from sloplab.models.run import CaseRecord
from sloplab.reporting.writers import read_run_jsonl
from sloplab.scoring.comparison import ClusterBootstrap, cluster_bootstrap_accuracy_ci

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "golden" / "issue-48-cluster"

SEED = 20260825
RESAMPLES = 2000
EXPECTED_CLUSTERS = 52


def _frozen_cluster_bootstrap() -> ClusterBootstrap:
    _, records = read_run_jsonl(FIXTURE_DIR / "records-0382566.jsonl")
    assert len(records) == 594, f"expected 594 frozen rows, got {len(records)}"
    pair_document = json.loads((FIXTURE_DIR / "canonical-pair-ids.json").read_text("utf-8"))
    pair_ids = {k: v for k, v in pair_document.items() if not k.startswith("_")}
    return cluster_bootstrap_accuracy_ci(
        records,
        resamples=RESAMPLES,
        ci=0.95,
        seed=SEED,
        pair_ids=pair_ids,
    )


def test_frozen_records_give_52_clusters_and_pinned_intervals() -> None:
    """The contract's pinned values, reproduced exactly at 4 decimals."""
    result = _frozen_cluster_bootstrap()
    assert result.clusters == EXPECTED_CLUSTERS

    rules = result.accuracy["rules-baseline"]
    assert round(rules[0], 4) == 0.7297, f"rules low {rules[0]!r}"
    assert round(rules[1], 4) == 0.8771, f"rules high {rules[1]!r}"

    graph = result.accuracy["evidence-graph-baseline"]
    assert round(graph[0], 4) == 0.4581, f"graph low {graph[0]!r}"
    assert round(graph[1], 4) == 0.6300, f"graph high {graph[1]!r}"

    assert list(result.paired_difference or {}) == ["evidence-graph-baseline - rules-baseline"]
    assert result.paired_difference is not None
    diff = result.paired_difference["evidence-graph-baseline - rules-baseline"]
    assert round(diff[0], 4) == 0.1679, f"diff low {diff[0]!r}"
    assert round(diff[1], 4) == 0.3547, f"diff high {diff[1]!r}"


def test_cluster_bootstrap_is_deterministic_and_row_level_differs() -> None:
    """Same inputs + seed reproduce byte-identical intervals; row-level does not."""
    first = _frozen_cluster_bootstrap()
    second = _frozen_cluster_bootstrap()
    assert first.as_dict() == second.as_dict()

    from sloplab.scoring.comparison import bootstrap_accuracy_ci

    _, records = read_run_jsonl(FIXTURE_DIR / "records-0382566.jsonl")
    row_level = {
        name: bootstrap_accuracy_ci(group, resamples=2000, ci=0.95, seed=SEED)
        for name, group in _by_evaluator(records).items()
    }
    # Backward compatibility: the row-level helper is unchanged and narrower.
    assert round(row_level["rules-baseline"][0], 4) == 0.7677
    assert round(row_level["rules-baseline"][2], 4) == 0.8552


def _by_evaluator(records: list[CaseRecord]) -> dict[str, list[CaseRecord]]:
    grouped: dict[str, list[CaseRecord]] = {}
    for record in records:
        grouped.setdefault(record.evaluator_name, []).append(record)
    return grouped
