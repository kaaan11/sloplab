"""Second reviewers receive neutral inputs and blank forms, without prior votes."""

from __future__ import annotations

import importlib
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def review(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("prepare_independent_review")


def population(review: Any) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    pairs = [
        {
            "mutation_id": f"m-{operator}-{index}",
            "operator": f"operator-{operator}",
            "report_a": "Visible A",
            "report_b": "Visible B",
        }
        for operator in range(6)
        for index in range(4)
    ]
    rows = [
        {
            "mutation_id": p["mutation_id"],
            "model": model,
            "status": "success",
            "vote": {
                "quality_changed": "yes" if model == review.MODELS[0] else "no",
                "action_changed": "no",
                "quality_reason": "PRIVATE_MODEL_VOTE",
            },
        }
        for p in pairs
        for model in review.MODELS
    ]
    return pairs, rows


def test_selection_balances_operators_and_is_order_invariant(review: Any) -> None:
    pairs, rows = population(review)
    selected = review.select_pairs(pairs, rows)
    assert len(selected) == 18
    assert set(Counter(p["operator"] for p in selected).values()) == {3}
    assert selected == review.select_pairs(list(reversed(pairs)), list(reversed(rows)))


def test_reviewer_packet_excludes_owner_and_model_answers(
    review: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare = importlib.import_module("prepare_heldout_inputs")
    monkeypatch.setattr(prepare, "PRIVATE_ROOT", tmp_path)
    pairs, rows = population(review)
    source = tmp_path / "source"
    views = {f"c{n:02d}": {"claims": [{"id": "C1"}]} for n in range(4, 13)}
    for card, view in views.items():
        dest = source / card
        dest.mkdir(parents=True)
        (dest / "input.json").write_text(json.dumps(view))
        (dest / "input.md").write_text("Visible neutral card")
    monkeypatch.setattr(review, "PACKET", source)
    monkeypatch.setattr(
        review, "load_owner_sheet", lambda: ({"private": "PRIVATE_OWNER_VOTE"}, "hash", views)
    )
    monkeypatch.setattr(review, "load_pairs", lambda: pairs)
    annotations = tmp_path / "annotations.jsonl"
    annotations.write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = tmp_path / "review"
    result = review.prepare(out, annotations)
    assert (result["cards"], result["pairs"]) == (9, 18)
    visible = out / "reviewer-packet"
    for path in visible.rglob("*"):
        if path.is_file():
            assert "PRIVATE_OWNER_VOTE" not in path.read_text()
            assert "PRIVATE_MODEL_VOTE" not in path.read_text()
    sheet = json.loads((visible / "judgment-sheet.json").read_text())
    assert sheet["judge"] == ""
    assert all(v["action"] == "" for v in sheet["cards"].values())
    assert all(v["quality_changed"] == "" for v in sheet["pairs"].values())
    assert not (visible / "admin-protocol.json").exists()
    assert (visible / "README.tr.md").is_file()
    with zipfile.ZipFile(out / "reviewer-packet.zip") as archive:
        expected = {
            "reviewer-packet/" + path.relative_to(visible).as_posix()
            for path in visible.rglob("*")
            if path.is_file()
        }
        assert set(archive.namelist()) == expected
        assert all("admin-protocol" not in name for name in archive.namelist())
