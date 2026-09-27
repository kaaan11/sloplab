"""Deterministic study analysis document builder (Dalga B, #49).

Single home for the legacy ``analysis.json`` computation consumed both by the
``sloplab study`` publisher and by the study-v02 lock test, so the two can
never drift apart. The document embeds the metric definition version (the
#37 analysis versioning) and the producing Python version (contract #49
item 3).
"""

from __future__ import annotations

import platform
from typing import Any

from sloplab.models.run import CaseRecord
from sloplab.reporting.analysis import ANALYSIS_DEFINITION_VERSION

#: Estimand sentence required by the issue #48 binding contract. The cluster
#: bootstrap interval is a sensitivity analysis WITHIN this fixed synthetic
#: collection: logical-report clusters are treated as exchangeable resampling
#: units. It is not external validity for real-world reports, and the cluster
#: count (52) is not an effective sample size (shared authorship and templates
#: also create cross-cluster dependence).
CLUSTER_BOOTSTRAP_ESTIMAND = (
    "within this fixed synthetic collection, treating logical-report clusters "
    "as exchangeable resampling units; the cluster count is not an effective "
    "sample size and the interval is not external validity for real reports"
)


def build_study_analysis(
    records: list[CaseRecord],
    *,
    bootstrap_resamples: int,
    bootstrap_ci: float,
    bootstrap_seed: int,
    pair_ids: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the study ``analysis.json`` document from scored case records.

    Metric bundles, paired comparisons, error taxonomies, per-operator and
    per-class breakdowns, and seeded bootstrap accuracy CIs are computed with
    the current metric definitions. Imports stay function-local so
    call-time patching of the scoring modules (as regression tests do)
    keeps working.

    The PRIMARY accuracy interval is the logical-report cluster bootstrap
    (issue #48 contract); the legacy row-level ``bootstrap_accuracy_ci`` block
    is kept for backward compatibility. ``pair_ids`` maps canonical case_id
    to the presentation ``pair_id`` of the canonical manifests; when given,
    clusters merge pair members into one logical report (60 fixtures -> 52).
    """
    from dataclasses import asdict

    from sloplab.scoring.comparison import (
        bootstrap_accuracy_ci,
        cluster_bootstrap_accuracy_ci,
        error_taxonomy,
        paired_win_loss,
        per_class_metrics,
        per_operator_metrics,
    )
    from sloplab.scoring.metrics import compute_metrics

    by_evaluator: dict[str, list[CaseRecord]] = {}
    for record in records:
        by_evaluator.setdefault(record.evaluator_name, []).append(record)
    bundles = {n: compute_metrics(rs, n) for n, rs in sorted(by_evaluator.items())}
    names = sorted(by_evaluator)
    comparisons = [
        paired_win_loss(by_evaluator[a], by_evaluator[b])
        for i, a in enumerate(names)
        for b in names[i + 1 :]
    ]
    taxonomies_full = {n: error_taxonomy(rs).as_dict() for n, rs in sorted(by_evaluator.items())}
    per_op = {
        n: {op: asdict(bundle) for op, bundle in per_operator_metrics(rs).items()}
        for n, rs in sorted(by_evaluator.items())
    }
    per_cls = {
        n: {cls: asdict(bundle) for cls, bundle in per_class_metrics(rs).items()}
        for n, rs in sorted(by_evaluator.items())
    }
    cis = {
        n: bootstrap_accuracy_ci(
            rs,
            resamples=bootstrap_resamples,
            ci=bootstrap_ci,
            seed=bootstrap_seed,
        )
        for n, rs in sorted(by_evaluator.items())
    }
    cluster = cluster_bootstrap_accuracy_ci(
        records,
        resamples=bootstrap_resamples,
        ci=bootstrap_ci,
        seed=bootstrap_seed,
        pair_ids=pair_ids,
    )
    cluster_document: dict[str, Any] = {
        "estimand": CLUSTER_BOOTSTRAP_ESTIMAND,
        "cluster_key": (
            "derived case: parent_id; canonical case: case_id; canonical "
            "presentation pair: pair_id (resolved through the parent for "
            "derived rows)"
        ),
        "clusters": cluster.clusters,
        "resamples": cluster.resamples,
        "seed": cluster.seed,
        "accuracy_ci": {n: {"low": lo, "high": hi} for n, (lo, hi) in cluster.accuracy.items()},
    }
    if cluster.paired_difference is not None:
        cluster_document["paired_difference_ci"] = {
            key: {"minuend": a, "subtrahend": b, "low": lo, "point": pt, "high": hi}
            for key, (lo, hi, pt) in cluster.paired_difference.items()
            for a, b in [key.split(" minus ")]
        }
    return {
        "metric_definition_version": ANALYSIS_DEFINITION_VERSION,
        "python_version": platform.python_version(),
        "bundles": {n: asdict(b) for n, b in bundles.items()},
        "paired_comparisons": [c.as_dict() for c in comparisons],
        "error_taxonomy": taxonomies_full,
        "per_operator": per_op,
        "per_class": per_cls,
        # PRIMARY interval (issue #48): logical-report cluster bootstrap.
        "cluster_bootstrap": cluster_document,
        # Backward compatibility: legacy row-level percentile bootstrap.
        "bootstrap_accuracy_ci": {
            n: {"low": lo, "point": pt, "high": hi} for n, (lo, pt, hi) in cis.items()
        },
    }
