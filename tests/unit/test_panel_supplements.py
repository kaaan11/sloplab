"""Supplement chains must preserve references, budgets and completed votes."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def supplement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, Path, Path, list[dict[str, Any]]]:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module("panel_supplements")
    base = tmp_path / "base.json"
    base.write_text('{"request_settings":{"model":{"temperature":0}}}')
    rows = [
        {"batch_id": "batch-000", "model": "model", "attempt": n, "status": "http_error"}
        for n in range(1, 4)
    ]
    folder = tmp_path / "coverage-supplements/edits/recovery-01"
    folder.mkdir(parents=True)
    protocol = {
        "schema_version": "panel-coverage-supplement-v1",
        "kind": "edits",
        "base_protocol_sha256": hashlib.sha256(base.read_bytes()).hexdigest(),
        "prior_rows_sha256": module.rows_sha256(rows),
        "request_settings": {"model": {"temperature": 0}},
        "max_attempts_per_slot": 3,
        "max_requests": 3,
        "slots": [{"batch_id": "batch-000", "model": "model", "previous_attempts": 3}],
    }
    (folder / "protocol.json").write_text(json.dumps(protocol))
    (folder / "requests.jsonl").write_text(
        json.dumps(
            {
                "batch_id": "batch-000",
                "model": "model",
                "attempt": 4,
                "supplement_attempt": 1,
                "source_run": "recovery-01",
                "status": "success",
            }
        )
        + "\n"
    )
    return module, tmp_path, base, rows


def test_supplement_keeps_original_failures_and_adds_one_success(
    supplement: tuple[Any, Path, Path, list[dict[str, Any]]],
) -> None:
    module, root, base, original = supplement
    combined, metadata, limits = module.load_supplements(root, "edits", base, original)
    assert combined[:3] == original
    assert len(combined) == 4
    assert combined[-1]["status"] == "success"
    assert metadata[0]["physical_requests"] == 1
    assert limits == {("batch-000", "model"): 6}


def test_supplement_rejects_changed_prior_failure(
    supplement: tuple[Any, Path, Path, list[dict[str, Any]]],
) -> None:
    module, root, base, rows = supplement
    rows[0]["status"] = "success"
    with pytest.raises(ValueError, match="prior history"):
        module.load_supplements(root, "edits", base, rows)


@pytest.mark.parametrize(
    "change", ["settings", "successful_slot", "cap", "post_success", "attempt"]
)
def test_supplement_rejects_unregistered_changes(
    supplement: tuple[Any, Path, Path, list[dict[str, Any]]], change: str
) -> None:
    module, root, base, rows = supplement
    folder = root / "coverage-supplements/edits/recovery-01"
    protocol = json.loads((folder / "protocol.json").read_text())
    extra = [json.loads((folder / "requests.jsonl").read_text())]
    if change == "settings":
        protocol["request_settings"]["model"]["temperature"] = 1
    elif change == "successful_slot":
        rows[-1]["status"] = "success"
        protocol["prior_rows_sha256"] = module.rows_sha256(rows)
    elif change == "cap":
        protocol["max_requests"] = 4
    elif change == "post_success":
        extra.append({**extra[0], "attempt": 5, "supplement_attempt": 2})
    else:
        extra[0]["attempt"] = 5
    (folder / "protocol.json").write_text(json.dumps(protocol))
    (folder / "requests.jsonl").write_text("".join(json.dumps(r) + "\n" for r in extra))
    with pytest.raises(ValueError):
        module.load_supplements(root, "edits", base, rows)
