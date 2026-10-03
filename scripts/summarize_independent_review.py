"""Validate returned human judgments and export aggregate-only offline comparisons."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from heldout_panel import FREEZE, PACKET, load_owner_sheet
from jsonschema import Draft202012Validator
from prepare_heldout_inputs import _inside_private
from prepare_independent_review import DEFAULT_ANNOTATIONS, select_pairs
from realized_edit_panel import MODELS, SCHEMA, load_pairs


def _unique_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _read(path: Path) -> Any:
    return json.loads(path.read_text(), object_pairs_hook=_unique_object)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_sheet(
    sheet: dict[str, Any],
    owner: dict[str, Any],
    views: dict[str, Any],
    pair_ids: set[str],
) -> None:
    if not isinstance(sheet, dict) or set(sheet) != {"judge", "judged_date", "cards", "pairs"}:
        raise ValueError("unexpected human sheet fields")
    judge = sheet["judge"]
    if not isinstance(judge, str) or not judge.strip():
        raise ValueError("second reviewer identifier is missing")
    if judge.strip().casefold() == owner["judge"].strip().casefold():
        raise ValueError("second reviewer identifier must differ from the first")
    if not isinstance(sheet["judged_date"], str):
        raise ValueError("review date must be an ISO date string")
    judged = date.fromisoformat(sheet["judged_date"])
    if judged.isoformat() != sheet["judged_date"] or judged > datetime.now(UTC).date():
        raise ValueError("review date is noncanonical or in the future")
    cards, pairs = sheet["cards"], sheet["pairs"]
    if not isinstance(cards, dict) or set(cards) != set(views):
        raise ValueError("returned card IDs differ from the packet")
    if not isinstance(pairs, dict) or set(pairs) != pair_ids:
        raise ValueError("returned pair IDs differ from the packet")
    for card_id, row in cards.items():
        if not isinstance(row, dict) or set(row) != {"action", "confidence", "rationale", "claims"}:
            raise ValueError("incomplete card judgment")
        if row["action"] not in {"verify", "request_specific_information", "likely_out_of_scope"}:
            raise ValueError("invalid card action")
        if row["confidence"] not in {"low", "medium", "high"}:
            raise ValueError("invalid card confidence")
        if not isinstance(row["rationale"], str) or not row["rationale"].strip():
            raise ValueError("missing card rationale")
        claims = row["claims"]
        if not isinstance(claims, dict) or set(claims) != {
            c["id"] for c in views[card_id]["claims"]
        }:
            raise ValueError("returned claim IDs differ from the input")
        if any(v not in {"supported", "missing", "contradictory"} for v in claims.values()):
            raise ValueError("invalid claim status")
    for row in pairs.values():
        if not isinstance(row, dict) or set(row) != {
            "quality_changed",
            "action_changed",
            "quality_reason",
            "action_reason",
        }:
            raise ValueError("incomplete pair judgment")
        if any(
            row[axis] not in {"yes", "no", "uncertain"}
            for axis in ("quality_changed", "action_changed")
        ):
            raise ValueError("invalid pair axis")
        if any(
            not isinstance(row[k], str) or not row[k].strip()
            for k in ("quality_reason", "action_reason")
        ):
            raise ValueError("missing pair rationale")


def category(quality: str | None, action: str | None) -> str:
    if quality not in {"yes", "no"} or action not in {"yes", "no"}:
        return "uncertain"
    if quality == action == "yes":
        return "both"
    if quality == "yes":
        return "quality_only"
    return "action_only" if action == "yes" else "neither"


def summarize(root: Path, annotations: Path = DEFAULT_ANNOTATIONS) -> dict[str, Any]:
    root = _inside_private(root)
    protocol_path = root / "admin-protocol.json"
    protocol = _read(protocol_path)
    packet = root / "reviewer-packet"
    sheet_path = packet / "judgment-sheet.json"
    owner, owner_sha, views = load_owner_sheet()
    if _read(FREEZE)["owner_sheet_sha256"] != owner_sha:
        raise ValueError("first reviewer differs from the frozen reference")
    if protocol["schema_version"] != "second-human-review-v1":
        raise ValueError("unknown review protocol")
    if protocol["annotations_sha256"] != _sha(annotations):
        raise ValueError("selection annotations changed")
    rows = [
        json.loads(line, object_pairs_hook=_unique_object)
        for line in annotations.read_text().splitlines()
    ]
    selected = select_pairs(load_pairs(), rows)
    expected_mapping = {}
    for n, pair in enumerate(selected, 1):
        text = (
            f"# Pair p{n:02d}\n\n## Report A\n\n{pair['report_a']}"
            f"\n\n## Report B\n\n{pair['report_b']}"
        )
        expected_mapping[f"p{n:02d}"] = {
            "mutation_id": pair["mutation_id"],
            "operator": pair["operator"],
            "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
    if (
        protocol["pair_mapping"] != expected_mapping
        or protocol["cards"] != len(views)
        or protocol["pairs"] != len(selected)
        or len(views) != 9
        or len(selected) != 18
    ):
        raise ValueError("review population or mapping changed")
    hashes = protocol["reviewer_file_sha256"]
    actual_files = {p.relative_to(packet).as_posix() for p in packet.rglob("*") if p.is_file()}
    if set(hashes) != actual_files or any(p.is_symlink() for p in packet.rglob("*")):
        raise ValueError("reviewer packet file inventory changed")
    for relative, expected in hashes.items():
        if relative != "judgment-sheet.json" and _sha(packet / relative) != expected:
            raise ValueError("reviewer input or instructions changed")
    for card_id in views:
        for name in ("input.json", "input.md"):
            if (packet / "cards" / card_id / name).read_bytes() != (
                PACKET / card_id / name
            ).read_bytes():
                raise ValueError("reviewer card differs from the first reviewer input")
    for pair_id, mapping in expected_mapping.items():
        if _sha(packet / "pairs" / pair_id / "input.md") != mapping["input_sha256"]:
            raise ValueError("reviewer pair differs from the selected public input")
    sheet = _read(sheet_path)
    validate_sheet(sheet, owner, views, set(expected_mapping))
    by_pair: dict[str, dict[str, Any]] = defaultdict(dict)
    validator = Draft202012Validator(SCHEMA)
    for row in rows:
        if row["status"] == "success":
            validator.validate(row["vote"])
            by_pair[row["mutation_id"]][row["model"]] = row["vote"]
        elif row["status"] not in {"http_error", "invalid_or_transport_error", "not_run"}:
            raise ValueError("unknown model annotation status")
    comparisons = {m: {"valid_pairs": 0, "quality_matches": 0, "action_matches": 0} for m in MODELS}
    majority = {
        axis: {"definite_pairs": 0, "matches": 0} for axis in ("quality_changed", "action_changed")
    }
    counts: Counter[str] = Counter()
    operators: dict[str, Counter[str]] = defaultdict(Counter)
    complete = category_matches = definite_categories = 0
    for opaque, mapping in expected_mapping.items():
        human = sheet["pairs"][opaque]
        human_category = category(human["quality_changed"], human["action_changed"])
        counts[human_category] += 1
        operators[mapping["operator"]][human_category] += 1
        votes = by_pair[mapping["mutation_id"]]
        for model, vote in votes.items():
            comparisons[model]["valid_pairs"] += 1
            comparisons[model]["quality_matches"] += (
                human["quality_changed"] == vote["quality_changed"]
            )
            comparisons[model]["action_matches"] += (
                human["action_changed"] == vote["action_changed"]
            )
        if len(votes) != len(MODELS):
            continue
        complete += 1
        majorities = {}
        for axis in majority:
            axis_counts = Counter(v[axis] for v in votes.values())
            definite = next((v for v in ("yes", "no") if axis_counts[v] >= 2), None)
            majorities[axis] = definite
            if definite is not None:
                majority[axis]["definite_pairs"] += 1
                majority[axis]["matches"] += human[axis] == definite
        if all(v is not None for v in majorities.values()):
            definite_categories += 1
            category_matches += human_category == category(
                majorities["quality_changed"], majorities["action_changed"]
            )
    return {
        "schema_version": "independent-human-review-aggregate-v1",
        "judged_date": sheet["judged_date"],
        "provenance": {
            "protocol_sha256": _sha(protocol_path),
            "second_sheet_sha256": _sha(sheet_path),
            "first_sheet_sha256": owner_sha,
            "annotations_sha256": _sha(annotations),
        },
        "validation": {
            "complete": True,
            "inputs_unchanged": True,
            "reviewer_identifier_differs": True,
            "scope": (
                "field completeness and input identity; rationale correctness is not adjudicated"
            ),
        },
        "independence_note": (
            "different human declared by user; blindness and independent authorship "
            "cannot be established from file checks"
        ),
        "cards": {
            "total": len(views),
            "action_matches_first_human": sum(
                sheet["cards"][c]["action"] == owner["cards"][c]["action"] for c in views
            ),
            "confidence_matches_first_human": sum(
                sheet["cards"][c]["confidence"] == owner["cards"][c]["confidence"] for c in views
            ),
            "claim_status_matches_first_human": sum(
                v == owner["cards"][c]["claims"][k]
                for c in views
                for k, v in sheet["cards"][c]["claims"].items()
            ),
            "claim_status_total": sum(len(v["claims"]) for v in sheet["cards"].values()),
        },
        "pairs": {
            "total": len(selected),
            "human_categories": dict(sorted(counts.items())),
            "by_operator": {k: dict(sorted(v.items())) for k, v in sorted(operators.items())},
            "complete_model_panels": complete,
            "individual_model_agreement": comparisons,
            "definite_model_majority_agreement": majority,
            "definite_model_category_pairs": definite_categories,
            "category_matches_definite_model_majority": category_matches,
        },
        "interpretation": (
            "descriptive agreement on nine exposed cards and 18 targeted pairs; "
            "no new ground truth, representative prevalence or general accuracy claim"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-root", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = json.dumps(summarize(args.packet_root, args.annotations), indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(result)
    print(result, end="")


if __name__ == "__main__":
    main()
