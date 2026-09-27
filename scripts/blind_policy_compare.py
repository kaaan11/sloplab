"""Issue #45 blind-policy comparison (recomputed for PR #33).

Compares rules-baseline against a blind always-needs_manual_review policy over
the committed v1-core-example records, using the project's own compute_metrics.
Usage: uv run python scripts/blind_policy_compare.py
"""

from __future__ import annotations

from pathlib import Path

from sloplab.models.enums import Decision
from sloplab.reporting.writers import read_run_jsonl
from sloplab.scoring.metrics import compute_metrics, decision_correct

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN = REPO_ROOT / "benchmarks" / "results" / "v1-core-example" / "run.jsonl"


def main() -> None:
    _, records = read_run_jsonl(RUN)
    rules = [r for r in records if r.evaluator_name == "rules-baseline"]
    blind = [
        r.model_copy(
            update={
                "evaluator_name": "blind-always-review",
                "decision": Decision.NEEDS_MANUAL_REVIEW,
                "correct": decision_correct(
                    r.model_copy(update={"decision": Decision.NEEDS_MANUAL_REVIEW})
                ),
            }
        )
        for r in rules
    ]
    rules_bundle = compute_metrics(rules, "rules-baseline")
    blind_bundle = compute_metrics(blind, "blind-always-review")
    rows = (
        ("mutation_detection_rate", "mutation_detection_rate"),
        ("decision_accuracy", "decision_accuracy"),
        ("false_reassurance_rate", "false_reassurance"),
        ("robustness_score", "robustness_score"),
    )
    print("| metric | rules-baseline | blind always-needs_manual_review |")
    print("|---|---|---|")
    for bundle_attr, _label in rows:
        print(
            f"| {bundle_attr} | {getattr(rules_bundle, bundle_attr)!r} | "
            f"{getattr(blind_bundle, bundle_attr)!r} |"
        )


if __name__ == "__main__":
    main()
