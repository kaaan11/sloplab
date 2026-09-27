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


def build_study_analysis(
    records: list[CaseRecord],
    *,
    bootstrap_resamples: int,
    bootstrap_ci: float,
    bootstrap_seed: int,
) -> dict[str, Any]:
    """Build the study ``analysis.json`` document from scored case records.

    Metric bundles, paired comparisons, error taxonomies, per-operator and
    per-class breakdowns, and seeded bootstrap accuracy CIs are computed with
    the current metric definitions. Imports stay function-local so
    call-time patching of the scoring modules (as regression tests do)
    keeps working.
    """
    from dataclasses import asdict

    from sloplab.scoring.comparison import (
        bootstrap_accuracy_ci,
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
    return {
        "metric_definition_version": ANALYSIS_DEFINITION_VERSION,
        "python_version": platform.python_version(),
        "bundles": {n: asdict(b) for n, b in bundles.items()},
        "paired_comparisons": [c.as_dict() for c in comparisons],
        "error_taxonomy": taxonomies_full,
        "per_operator": per_op,
        "per_class": per_cls,
        "bootstrap_accuracy_ci": {
            n: {"low": lo, "point": pt, "high": hi} for n, (lo, pt, hi) in cis.items()
        },
    }
