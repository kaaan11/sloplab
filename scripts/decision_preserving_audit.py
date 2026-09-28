"""Inventory authored decision-preserving mutations and evidence-list conflicts.

This is a provenance audit, not an independent semantic relabeling. It makes
the denominator and the source of every count explicit.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import yaml

from sloplab.models.enums import ReportClass, canonical_expected_decision
from sloplab.mutations.base import get_operator

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    corpus = REPO_ROOT / "corpus/canonical"
    variants = REPO_ROOT / "benchmarks/results/v1-core-example/adversarial"
    by_operator: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    examples: list[str] = []
    for path in sorted(variants.glob("**/mutation-manifest.yaml")):
        mutation = yaml.safe_load(path.read_text(encoding="utf-8"))
        parent_id = mutation["parent_id"]
        parent_path = corpus / parent_id.removeprefix("canonical-") / "manifest.yaml"
        parent = yaml.safe_load(parent_path.read_text(encoding="utf-8"))
        expected = canonical_expected_decision(ReportClass(parent["report_class"]))
        if mutation["expected_decision"] != expected:
            continue
        operator = mutation["operator"]
        by_operator[operator] += 1
        counts["decision_preserving"] += 1
        spec = get_operator(operator).spec
        counts["negative_authored_dimension_delta"] += int(
            any(delta < 0 for delta in spec.dimension_deltas.values())
        )
        if (
            operator == "remove_affected_version"
            and "affected_versions" in parent["ground_truth"]["required_evidence"]
        ):
            counts["removes_listed_required_version"] += 1
            examples.append(mutation["id"])
    if counts["decision_preserving"] != 141:
        raise AssertionError(f"unexpected decision-preserving count: {counts}")
    print(
        json.dumps(
            {
                "population": "committed v1-core-example; authored labels, not independent review",
                "counts": dict(counts),
                "by_operator": dict(sorted(by_operator.items())),
                "required_version_examples": examples,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
