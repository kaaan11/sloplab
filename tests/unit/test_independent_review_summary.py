"""Returned judgments must preserve inputs, privacy and incomplete-panel denominators."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_independent_review_packet import population


def setup_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, failed_model: bool = False
) -> tuple[Any, Path, Path]:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    review = importlib.import_module("prepare_independent_review")
    summary = importlib.import_module("summarize_independent_review")
    prepare = importlib.import_module("prepare_heldout_inputs")
    monkeypatch.setattr(prepare, "PRIVATE_ROOT", tmp_path)
    pairs, rows = population(review)
    for row in rows:
        row["vote"]["action_reason"] = "PRIVATE_MODEL_REASON"
    if failed_model:
        for row in rows:
            if row["model"] == review.MODELS[0]:
                row["status"] = "http_error"
                del row["vote"]
    source = tmp_path / "inputs"
    views = {f"c{n:02d}": {"claims": [{"id": "C1"}]} for n in range(4, 13)}
    owner: dict[str, Any] = {"judge": "PRIVATE_FIRST_NAME", "cards": {}}
    for card_id, view in views.items():
        dest = source / card_id
        dest.mkdir(parents=True)
        (dest / "input.json").write_text(json.dumps(view))
        (dest / "input.md").write_text("PRIVATE_FRESH_INPUT")
        owner["cards"][card_id] = {
            "action": "verify",
            "confidence": "high",
            "rationale": "PRIVATE_FIRST_REASON",
            "claims": {"C1": "supported"},
        }
    for module in (review, summary):
        monkeypatch.setattr(module, "PACKET", source)
        monkeypatch.setattr(module, "load_owner_sheet", lambda: (owner, "owner-hash", views))
        monkeypatch.setattr(module, "load_pairs", lambda: pairs)
    freeze = tmp_path / "freeze.json"
    freeze.write_text('{"owner_sheet_sha256":"owner-hash"}')
    monkeypatch.setattr(summary, "FREEZE", freeze)
    annotations = tmp_path / "annotations.jsonl"
    annotations.write_text("".join(json.dumps(row) + "\n" for row in rows))
    root = tmp_path / "review"
    review.prepare(root, annotations)
    sheet_path = root / "reviewer-packet/judgment-sheet.json"
    sheet = json.loads(sheet_path.read_text())
    sheet.update(judge="PRIVATE_SECOND_NAME", judged_date="2026-10-03")
    for card_id, row in sheet["cards"].items():
        row.update(owner["cards"][card_id])
        row["rationale"] = "PRIVATE_SECOND_REASON"
    sheet["cards"]["c04"]["claims"] = {"C1": "missing"}
    for row in sheet["pairs"].values():
        row.update(
            quality_changed="yes",
            action_changed="no",
            quality_reason="PRIVATE_SECOND_REASON",
            action_reason="PRIVATE_SECOND_REASON",
        )
    sheet_path.write_text(json.dumps(sheet))
    return summary, root, annotations


def test_summary_counts_human_disagreement_and_excludes_private_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, root, annotations = setup_review(tmp_path, monkeypatch)
    result = module.summarize(root, annotations)
    assert result["cards"] == {
        "total": 9,
        "action_matches_first_human": 9,
        "confidence_matches_first_human": 9,
        "claim_status_matches_first_human": 8,
        "claim_status_total": 9,
    }
    assert result["pairs"]["human_categories"] == {"quality_only": 18}
    assert result["pairs"]["definite_model_majority_agreement"] == {
        "quality_changed": {"definite_pairs": 18, "matches": 0},
        "action_changed": {"definite_pairs": 18, "matches": 18},
    }
    assert "PRIVATE_" not in json.dumps(result)


def test_missing_model_votes_do_not_become_complete_majorities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, root, annotations = setup_review(tmp_path, monkeypatch, failed_model=True)
    result = module.summarize(root, annotations)["pairs"]
    assert result["complete_model_panels"] == 0
    assert result["definite_model_category_pairs"] == 0
    assert result["definite_model_majority_agreement"]["action_changed"]["definite_pairs"] == 0
    assert result["individual_model_agreement"][module.MODELS[0]]["valid_pairs"] == 0
    assert result["individual_model_agreement"][module.MODELS[1]]["valid_pairs"] == 18


@pytest.mark.parametrize(
    "change", ["same_judge", "claim_id", "pair_id", "blank_reason", "axis", "date"]
)
def test_incomplete_or_invalid_return_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    module, root, annotations = setup_review(tmp_path, monkeypatch)
    path = root / "reviewer-packet/judgment-sheet.json"
    sheet = json.loads(path.read_text())
    if change == "same_judge":
        sheet["judge"] = " private_first_name "
    elif change == "claim_id":
        sheet["cards"]["c04"]["claims"] = {"unknown": "missing"}
    elif change == "pair_id":
        del sheet["pairs"]["p01"]
    elif change == "blank_reason":
        sheet["pairs"]["p01"]["action_reason"] = " "
    elif change == "axis":
        sheet["pairs"]["p01"]["quality_changed"] = "maybe"
    else:
        sheet["judged_date"] = "9999-12-31"
    path.write_text(json.dumps(sheet))
    with pytest.raises(ValueError):
        module.summarize(root, annotations)


def test_changed_card_is_rejected_even_if_admin_hash_is_rewritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, root, annotations = setup_review(tmp_path, monkeypatch)
    relative = "cards/c04/input.md"
    path = root / "reviewer-packet" / relative
    path.write_text("changed scenario")
    protocol_path = root / "admin-protocol.json"
    protocol = json.loads(protocol_path.read_text())
    protocol["reviewer_file_sha256"][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    protocol_path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="first reviewer input"):
        module.summarize(root, annotations)


def test_duplicate_json_field_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module, root, annotations = setup_review(tmp_path, monkeypatch)
    path = root / "reviewer-packet/judgment-sheet.json"
    path.write_text('{"judge":"one","judge":"two"}')
    with pytest.raises(ValueError, match="duplicate JSON field"):
        module.summarize(root, annotations)
