"""Issue #45 fixed-action controls and parent-child transition audit.

Compares rules-baseline against all three constant policies over the committed
v1-core-example records, using the project's own compute_metrics. The paired
diagnostics retain canonical parent decisions within the same repeat.
Usage: uv run python scripts/blind_policy_compare.py
"""

from __future__ import annotations

from pathlib import Path

from sloplab.models.enums import Decision
from sloplab.models.run import CaseRecord
from sloplab.reporting.writers import read_run_jsonl
from sloplab.scoring.audits import audit_decision_changing_mutations
from sloplab.scoring.metrics import compute_metrics, decision_correct

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN = REPO_ROOT / "benchmarks" / "results" / "v1-core-example" / "run.jsonl"


def main() -> None:
    _, records = read_run_jsonl(RUN)
    rules = [r for r in records if r.evaluator_name == "rules-baseline"]
    policies: dict[str, list[CaseRecord]] = {"rules-baseline": rules}
    for action in Decision:
        name = f"always-{action.value}"
        policies[name] = [
            r.model_copy(
                update={
                    "evaluator_name": name,
                    "decision": action,
                    "confidence": 0.5,
                    "correct": decision_correct(r.model_copy(update={"decision": action})),
                }
            )
            for r in rules
        ]
    bundles = {name: compute_metrics(rows, name) for name, rows in policies.items()}
    rows = (
        ("mutation_detection_rate", "mutation_detection_rate"),
        ("decision_accuracy", "decision_accuracy"),
        ("false_reassurance_rate", "false_reassurance"),
        ("robustness_score", "robustness_score"),
    )
    names = list(policies)
    print("| metric | " + " | ".join(names) + " |")
    print("|---|" + "---:|" * len(names))
    for bundle_attr, _label in rows:
        print(
            "| "
            + bundle_attr
            + " | "
            + " | ".join(repr(getattr(bundles[name], bundle_attr)) for name in names)
            + " |"
        )
    print("\n| paired diagnostic | " + " | ".join(names) + " |")
    print("|---|" + "---:|" * len(names))
    audits = {
        name: audit_decision_changing_mutations(policy_rows).as_dict()
        for name, policy_rows in policies.items()
    }
    for metric in (
        "eligible_children",
        "paired",
        "missing_parent",
        "both_correct_rate",
        "actual_decision_change_rate",
        "child_correct_given_parent_correct",
        "deferral_rate",
    ):
        print(
            "| " + metric + " | " + " | ".join(repr(audits[name][metric]) for name in names) + " |"
        )


if __name__ == "__main__":
    main()
