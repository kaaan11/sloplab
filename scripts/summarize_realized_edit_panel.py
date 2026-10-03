"""Aggregate realized-edit votes; export annotations only for the public v1 cases."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from realized_edit_panel import MAX_ATTEMPTS, MODELS, PROTOCOL, RESULTS, SCHEMA, load_pairs


def normalize_requests(
    raw_rows: list[dict[str, Any]], protocol: dict[str, Any], pairs: list[dict[str, str]]
) -> list[dict[str, Any]]:
    expected_ids = {p["mutation_id"] for p in pairs}
    reverse: dict[str, str] = {}
    for batch, ids in protocol["batch_mapping"].items():
        for pair_id in ids:
            if pair_id in reverse or pair_id not in expected_ids:
                raise ValueError("unexpected or duplicate public pair ID in protocol")
            reverse[pair_id] = batch
    if set(reverse) != expected_ids or protocol["model_ids"] != list(MODELS):
        raise ValueError("protocol differs from public pair population or model panel")
    histories: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    successful: dict[tuple[str, str], dict[str, Any]] = {}
    validator = Draft202012Validator(SCHEMA)
    for row in raw_rows:
        key = row["batch_id"], row["model"]
        if key[0] not in protocol["batch_mapping"] or key[1] not in MODELS:
            raise ValueError("unknown batch or model")
        history = histories[key]
        if row["attempt"] != len(history) + 1 or len(history) >= MAX_ATTEMPTS:
            raise ValueError("duplicate or nonsequential attempt")
        if any(r["status"] == "success" for r in history):
            raise ValueError("request after successful batch")
        history.append(row)
        if row["status"] != "success":
            continue
        ids = [item["mutation_id"] for item in row["votes"]]
        expected = protocol["batch_mapping"][key[0]]
        if len(ids) != len(expected) or set(ids) != set(expected):
            raise ValueError("missing or duplicate annotations in batch")
        for item in row["votes"]:
            validator.validate(item["vote"])
            successful[item["mutation_id"], key[1]] = item["vote"]
    output = []
    for pair_id in sorted(expected_ids):
        for model in MODELS:
            row = {"mutation_id": pair_id, "model": model}
            vote = successful.get((pair_id, model))
            if vote is not None:
                row.update(status="success", vote=vote)
            else:
                history = histories.get((reverse[pair_id], model), [])
                row["status"] = history[-1]["status"] if history else "not_run"
            output.append(row)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="export normalized public-corpus annotations")
    parser.add_argument("--bundle", type=Path, help="recompute from a published annotation bundle")
    args = parser.parse_args()
    pairs = load_pairs()
    by_id = {pair["mutation_id"]: pair for pair in pairs}
    protocol_path = args.bundle / "protocol.json" if args.bundle else PROTOCOL
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    expected_hashes = {
        p["mutation_id"]: hashlib.sha256(
            json.dumps({k: p[k] for k in ("report_a", "report_b")}, sort_keys=True).encode()
        ).hexdigest()
        for p in pairs
    }
    if protocol["input_sha256"] != expected_hashes or protocol["model_ids"] != list(MODELS):
        raise ValueError("protocol differs from current public inputs or model panel")
    if args.bundle:
        rows = [
            json.loads(line)
            for line in (args.bundle / "annotations.jsonl").read_text().splitlines()
        ]
        accounting = protocol["request_accounting"]
        public_protocol = protocol
    else:
        raw_rows = [json.loads(line) for line in RESULTS.read_text(encoding="utf-8").splitlines()]
        rows = normalize_requests(raw_rows, protocol, pairs)
        accounting = {
            "physical_requests": len(raw_rows),
            "physical_request_status": dict(Counter(r["status"] for r in raw_rows)),
        }
        public_protocol = {
            **protocol,
            "raw_ledger_sha256": hashlib.sha256(RESULTS.read_bytes()).hexdigest(),
            "request_accounting": accounting,
        }
    by_pair: dict[str, list[dict]] = defaultdict(list)
    model_status: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = row["mutation_id"], row["model"]
        if row["mutation_id"] not in by_id or row["model"] not in MODELS or key in seen:
            raise ValueError(f"unexpected or duplicate vote key: {key}")
        seen.add(key)
        if row["status"] == "success":
            Draft202012Validator(SCHEMA).validate(row["vote"])
        model_status[f"{row['model']}:{row['status']}"] += 1
        by_pair[row["mutation_id"]].append(row)
    if len(seen) != len(pairs) * len(MODELS):
        raise ValueError("annotation bundle is missing planned slots")
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
    summary = {
        "population": "141 public decision-preserving realized edits",
        "annotation": "exploratory model votes; authored labels hidden",
        "models": list(MODELS),
        "planned_votes": len(rows),
        **accounting,
        "successful_votes": sum(r["status"] == "success" for r in rows),
        "model_status": dict(sorted(model_status.items())),
        "majority_categories": dict(sorted(categories.items())),
        "pairs_with_any_dissent": dissent,
        "uncertain_pairs": uncertain,
        "pairs_with_failed_vote": failed_pairs,
        "axis_vote_counts": {axis: dict(counts) for axis, counts in axis_votes.items()},
        "by_operator": {
            name: dict(sorted(counts.items())) for name, counts in sorted(by_operator.items())
        },
    }
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        (args.out / "annotations.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        )
        (args.out / "protocol.json").write_text(json.dumps(public_protocol, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
