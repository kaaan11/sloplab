"""E4b: historical recomputation is reproducible; every diff has a reason."""

from __future__ import annotations

import json
from pathlib import Path

from sloplab.reporting.writers import metrics_to_dict, read_run_jsonl
from sloplab.scoring.metrics import compute_metrics

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "benchmarks" / "results" / "v1-core-example"

# Reason codes for legacy-vs-current differences. Any metric that differs
# between a historical artifact and a fresh recomputation must name one.
REASON_PAIRED_FIX = "paired susceptibility fix (E4a)"
REASON_CLOSED_BIN = "closed-bin ECE fix (E4a)"
REASON_COVERAGE_ENVELOPE = "coverage envelope added (E4a)"
REASON_UNCHANGED = "unchanged"


def _legacy_metrics(name: str) -> dict:
    return json.loads((EXAMPLE / f"metrics-{name}.json").read_text(encoding="utf-8"))


def _recomputed() -> dict[str, dict]:
    _, records = read_run_jsonl(EXAMPLE / "run.jsonl")
    by_evaluator: dict[str, list] = {}
    for record in records:
        by_evaluator.setdefault(record.evaluator_name, []).append(record)
    return {
        name: metrics_to_dict(compute_metrics(rs, name))
        for name, rs in sorted(by_evaluator.items())
    }


def test_recomputation_is_deterministic() -> None:
    """Same raw records recompute to identical bundles, twice."""
    first = _recomputed()
    second = _recomputed()
    assert first == second


def test_every_difference_has_a_recorded_reason() -> None:
    """Historical artifacts vs fresh code: diffs named, rest identical."""
    current = _recomputed()
    reasons: dict[str, dict[str, str]] = {}
    for name, new in sorted(current.items()):
        old = _legacy_metrics(name)
        table: dict[str, str] = {}
        for key, new_value in sorted(new.items()):
            if key == "metric_coverage":
                assert key not in old
                table[key] = REASON_COVERAGE_ENVELOPE
                continue
            old_value = old.get(key)
            if key == "presentation_susceptibility":
                table[key] = REASON_PAIRED_FIX if old_value != new_value else REASON_UNCHANGED
            elif key == "calibration_error":
                table[key] = REASON_CLOSED_BIN if old_value != new_value else REASON_UNCHANGED
            else:
                assert old_value == new_value, f"{name}.{key}: {old_value} != {new_value}"
                table[key] = REASON_UNCHANGED
            assert table[key] in {
                REASON_PAIRED_FIX,
                REASON_CLOSED_BIN,
                REASON_COVERAGE_ENVELOPE,
                REASON_UNCHANGED,
            }
        reasons[name] = table
    # Pinned expectations on the committed bundle: only the paired fix bites,
    # and only where unbalanced pairs exist.
    assert reasons["rules-baseline"]["presentation_susceptibility"] == REASON_PAIRED_FIX
    assert current["rules-baseline"]["presentation_susceptibility"] == 0.0
    assert reasons["oracle"]["presentation_susceptibility"] == REASON_UNCHANGED
    assert reasons["rules-baseline"]["calibration_error"] == REASON_UNCHANGED
    assert reasons["oracle"]["calibration_error"] == REASON_UNCHANGED
    assert reasons["rules-baseline"]["decision_accuracy"] == REASON_UNCHANGED
    assert set(reasons) == {"oracle", "rules-baseline"}
