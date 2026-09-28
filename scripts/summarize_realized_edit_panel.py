"""Aggregate private realized-edit votes without publishing per-case annotations."""

from __future__ import annotations

import json
from collections import Counter, defaultdict

from realized_edit_panel import MODELS, RESULTS, load_pairs


def main() -> None:
    pairs = load_pairs()
    by_id = {pair["mutation_id"]: pair for pair in pairs}
    rows = [json.loads(line) for line in RESULTS.read_text(encoding="utf-8").splitlines()]
    if len(rows) != len(pairs) * len(MODELS):
        raise ValueError("private ledger has incomplete request coverage")
    by_pair: dict[str, list[dict]] = defaultdict(list)
    model_status: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = row["mutation_id"], row["model"]
        if row["mutation_id"] not in by_id or row["model"] not in MODELS or key in seen:
            raise ValueError(f"unexpected or duplicate vote key: {key}")
        seen.add(key)
        model_status[f"{row['model']}:{row['status']}"] += 1
        by_pair[row["mutation_id"]].append(row)
    categories: Counter[str] = Counter()
    by_operator: dict[str, Counter[str]] = defaultdict(Counter)
    axis_votes: dict[str, Counter[str]] = defaultdict(Counter)
    dissent = uncertain = failed_pairs = 0
    for mutation_id, votes in by_pair.items():
        valid = [row["vote"] for row in votes if row["status"] == "success"]
        if len(valid) != len(MODELS):
            failed_pairs += 1
            category = "incomplete"
        else:
            quality = Counter(vote["quality_changed"] for vote in valid)
            action = Counter(vote["action_changed"] for vote in valid)
            for value, count in quality.items():
                axis_votes["quality"][value] += count
            for value, count in action.items():
                axis_votes["action"][value] += count
            if max(quality.values()) < 3 or max(action.values()) < 3:
                dissent += 1
            quality_majority = next((v for v in ("yes", "no") if quality[v] >= 2), None)
            action_majority = next((v for v in ("yes", "no") if action[v] >= 2), None)
            if quality_majority is None or action_majority is None:
                category = "uncertain"
                uncertain += 1
            else:
                category = (
                    "both"
                    if quality_majority == action_majority == "yes"
                    else "quality_only"
                    if quality_majority == "yes"
                    else "action_only"
                    if action_majority == "yes"
                    else "neither"
                )
        categories[category] += 1
        by_operator[by_id[mutation_id]["operator"]][category] += 1
    print(
        json.dumps(
            {
                "population": "141 public decision-preserving realized edits",
                "annotation": "exploratory model votes; authored labels hidden",
                "models": list(MODELS),
                "requested": len(rows),
                "model_status": dict(sorted(model_status.items())),
                "majority_categories": dict(sorted(categories.items())),
                "pairs_with_any_dissent": dissent,
                "uncertain_pairs": uncertain,
                "pairs_with_failed_vote": failed_pairs,
                "axis_vote_counts": {axis: dict(counts) for axis, counts in axis_votes.items()},
                "by_operator": {
                    name: dict(sorted(counts.items()))
                    for name, counts in sorted(by_operator.items())
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
