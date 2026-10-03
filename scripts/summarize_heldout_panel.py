"""Compare private card votes to frozen owner judgments; print only aggregates."""

from __future__ import annotations

import hashlib
import json
from collections import Counter

from heldout_panel import FREEZE, MANIFEST, MODELS, RESULTS, ROOT, _output_schema, load_owner_sheet
from jsonschema import Draft202012Validator


def summarize() -> dict:
    owner, owner_sha, views = load_owner_sheet()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    if owner_sha != freeze["owner_sheet_sha256"] or list(MODELS) != freeze["model_ids"]:
        raise ValueError("owner judgment or model set differs from frozen panel")
    if json.loads(MANIFEST.read_text())["input_sha256"] != freeze["input_sha256"]:
        raise ValueError("private input manifest differs from frozen panel")
    rows = [json.loads(line) for line in RESULTS.read_text(encoding="utf-8").splitlines()]
    original_requests = len(rows)
    supplemental_path = ROOT / "panel-supplemental.jsonl"
    supplemental_protocol_path = ROOT / "panel-supplemental-protocol.json"
    supplemental_hashes = {}
    if supplemental_path.exists():
        protocol = json.loads(supplemental_protocol_path.read_text(encoding="utf-8"))
        if (
            protocol["owner_sheet_sha256"] != owner_sha
            or protocol["original_freeze_sha256"] != hashlib.sha256(FREEZE.read_bytes()).hexdigest()
        ):
            raise ValueError("supplement differs from original owner reference")
        extra = [json.loads(line) for line in supplemental_path.read_text().splitlines()]
        if len(extra) > protocol["max_requests"]:
            raise ValueError("supplement exceeds registered request cap")
        slots = {(s["card_id"], s["model"]) for s in protocol["slots"]}
        if any((r["card_id"], r["model"]) not in slots for r in extra):
            raise ValueError("unknown supplemental slot")
        rows.extend(extra)
        supplemental_hashes = {
            "protocol_sha256": hashlib.sha256(supplemental_protocol_path.read_bytes()).hexdigest(),
            "ledger_sha256": hashlib.sha256(supplemental_path.read_bytes()).hexdigest(),
        }
    successful: dict[tuple[str, str], dict] = {}
    attempts: Counter[tuple[str, str]] = Counter()
    statuses: Counter[str] = Counter()
    for row in rows:
        card_id, model = row["card_id"], row["model"]
        key = card_id, model
        if card_id not in views or model not in MODELS or key in successful:
            raise ValueError("unexpected or post-success request in ledger")
        attempts[key] += 1
        if row["attempt"] != attempts[key]:
            raise ValueError("nonsequential or duplicate attempt")
        statuses[row["status"]] += 1
        if row["status"] == "success":
            claim_ids = [claim["id"] for claim in views[card_id]["claims"]]
            vote = row["vote"]
            Draft202012Validator(_output_schema(claim_ids)).validate(vote)
            if {c["claim_id"] for c in vote["claims"]} != set(claim_ids):
                raise ValueError("model vote has missing or duplicate claims")
            successful[key] = vote
    model_totals = {}
    for model in MODELS:
        votes = [(card, vote) for (card, name), vote in successful.items() if name == model]
        action_match = claim_match = claim_total = confidence_match = 0
        transitions: Counter[str] = Counter()
        for card_id, vote in votes:
            reference = owner["cards"][card_id]
            action_match += vote["action"] == reference["action"]
            confidence_match += vote["confidence"] == reference["confidence"]
            transitions[f"{reference['action']} -> {vote['action']}"] += 1
            for claim in vote["claims"]:
                claim_total += 1
                claim_match += claim["status"] == reference["claims"][claim["claim_id"]]
        model_totals[model] = {
            "valid_votes": len(votes),
            "owner_action_agreement": action_match,
            "owner_claim_status_agreement": claim_match,
            "claim_status_total": claim_total,
            "owner_confidence_agreement": confidence_match,
            "action_transitions": dict(transitions),
        }
    complete_cards = 0
    cards_with_action_disagreement = cards_with_claim_disagreement = 0
    for card in views:
        votes = [successful[card, model] for model in MODELS if (card, model) in successful]
        if len(votes) != len(MODELS):
            continue
        complete_cards += 1
        reference = owner["cards"][card]
        cards_with_action_disagreement += any(v["action"] != reference["action"] for v in votes)
        cards_with_claim_disagreement += any(
            claim["status"] != reference["claims"][claim["claim_id"]]
            for vote in votes
            for claim in vote["claims"]
        )
    return {
        "schema_version": "private-panel-aggregate-v0.1",
        "reference": "frozen owner blind judgments; descriptive agreement",
        "owner_sheet_sha256": owner_sha,
        "freeze_sha256": hashlib.sha256(FREEZE.read_bytes()).hexdigest(),
        "ledger_sha256": hashlib.sha256(RESULTS.read_bytes()).hexdigest(),
        "physical_requests": len(rows),
        "original_physical_requests": original_requests,
        "supplemental_physical_requests": len(rows) - original_requests,
        "supplemental_hashes": supplemental_hashes,
        "request_statuses": dict(statuses),
        "planned_votes": len(views) * len(MODELS),
        "valid_votes": len(successful),
        "complete_cards": complete_cards,
        "cards_with_any_action_disagreement": cards_with_action_disagreement,
        "cards_with_any_claim_disagreement": cards_with_claim_disagreement,
        "models": model_totals,
    }


def main() -> None:
    print(json.dumps(summarize(), indent=2))


if __name__ == "__main__":
    main()
