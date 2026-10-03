"""Private panel gates: free pricing, pre-vote owner input, and shared pacing."""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def panel(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("heldout_panel")


def test_catalog_rejects_priced_free_variant(
    panel: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries: list[dict[str, Any]] = [
        {
            "id": model,
            "pricing": {"prompt": "0", "completion": "0", "request": "0"},
            "supported_parameters": ["structured_outputs"],
        }
        for model in panel.MODELS
    ]
    entries[1]["pricing"]["completion"] = "0.00001"
    monkeypatch.setattr(
        panel.urllib.request,
        "urlopen",
        lambda *args, **kwargs: io.BytesIO(json.dumps({"data": entries}).encode()),
    )
    with pytest.raises(ValueError, match="zero-cost free models"):
        panel._catalog_models()


def test_blank_owner_sheet_stops_before_catalog_or_dispatch(
    panel: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepare = importlib.import_module("prepare_heldout_inputs")
    monkeypatch.setattr(prepare, "PRIVATE_ROOT", tmp_path)
    sheet = tmp_path / "judgment-sheet.yaml"
    sheet.write_text("judge: ''\njudged_date: ''\ncards: {}\n")
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"input_sha256": {}}')
    monkeypatch.setattr(panel, "SHEET", sheet)
    monkeypatch.setattr(panel, "MANIFEST", manifest)
    monkeypatch.setattr(sys, "argv", ["heldout_panel.py", "--run"])

    def unexpected_catalog() -> None:
        pytest.fail("provider preflight reached before owner's blind judgment")

    monkeypatch.setattr(panel, "_catalog_models", unexpected_catalog)
    with pytest.raises(ValueError, match="owner judge is missing"):
        panel.main()


def test_concurrent_panel_workers_share_request_spacing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    pacing = importlib.import_module("panel_pacing")
    clock = [0.0]
    waits: list[float] = []

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(pacing, "_last_start", None)
    monkeypatch.setattr(pacing.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(pacing.time, "sleep", sleep)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: pacing.pace_request(), range(6)))
    assert len(waits) == 5
    assert all(wait >= pacing.MIN_INTERVAL_SECONDS - 1e-9 for wait in waits)


def test_resume_refuses_changed_owner_reference(
    panel: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze = tmp_path / "freeze.json"
    freeze.write_text('{"owner_sheet_sha256":"original"}')
    results = tmp_path / "results.jsonl"
    original = '{"untouched":"ledger"}\n'
    results.write_text(original)
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"input_sha256":{}}')
    monkeypatch.setattr(panel, "FREEZE", freeze)
    monkeypatch.setattr(panel, "RESULTS", results)
    monkeypatch.setattr(panel, "MANIFEST", manifest)
    monkeypatch.setattr(
        panel, "load_owner_sheet", lambda: ({"judged_date": "2026-10-03"}, "changed", {})
    )
    monkeypatch.setattr(panel, "_catalog_models", lambda: {m: {} for m in panel.MODELS})
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-test-key")
    monkeypatch.setattr(sys, "argv", ["heldout_panel.py", "--run", "--resume"])
    with pytest.raises(ValueError, match="frozen owner_sheet_sha256"):
        panel.main()
    assert results.read_text() == original


def test_public_annotation_export_rejects_unknown_pair(
    panel: ModuleType,
) -> None:
    summary = importlib.import_module("summarize_realized_edit_panel")
    pairs = [{"mutation_id": pair_id} for pair_id in ("mut-a", "mut-b", "mut-c")]
    protocol = {
        "batch_mapping": {"batch-000": [p["mutation_id"] for p in pairs]},
        "model_ids": list(summary.MODELS),
    }
    row = {
        "batch_id": "batch-000",
        "model": summary.MODELS[0],
        "attempt": 1,
        "status": "success",
        "votes": [{"mutation_id": "c04", "vote": {}}],
    }
    with pytest.raises(ValueError, match="missing or duplicate annotations"):
        summary.normalize_requests([row], protocol, pairs)


def test_retry_produces_one_annotation_per_pair_and_model(panel: ModuleType) -> None:
    summary = importlib.import_module("summarize_realized_edit_panel")
    pairs = [{"mutation_id": pair_id} for pair_id in ("mut-a", "mut-b", "mut-c")]
    protocol = {
        "batch_mapping": {"batch-000": [p["mutation_id"] for p in pairs]},
        "model_ids": list(summary.MODELS),
    }
    vote = {
        "quality_changed": "yes",
        "action_changed": "no",
        "quality_reason": "Changed clarity",
        "action_reason": "Verification inputs remain available",
    }
    rows = [
        {"batch_id": "batch-000", "model": summary.MODELS[0], "attempt": 1, "status": "http_error"},
        {
            "batch_id": "batch-000",
            "model": summary.MODELS[0],
            "attempt": 2,
            "status": "success",
            "votes": [{"mutation_id": p["mutation_id"], "vote": vote} for p in pairs],
        },
    ]
    normalized = summary.normalize_requests(rows, protocol, pairs)
    assert len(normalized) == 9
    assert sum(row["status"] == "success" for row in normalized) == 3
    assert sum(row["status"] == "not_run" for row in normalized) == 6


def test_realized_resume_preserves_api_credential(
    panel: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = importlib.import_module("realized_edit_panel")
    pairs = [
        {"mutation_id": "mut-a", "report_a": "a", "report_b": "b"},
    ]
    monkeypatch.setattr(runner, "load_pairs", lambda: pairs)
    monkeypatch.setattr(runner, "_catalog_models", lambda models: {})
    monkeypatch.setattr(runner, "PROTOCOL", tmp_path / "protocol.json")
    monkeypatch.setattr(runner, "RESULTS", tmp_path / "votes.jsonl")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-test-key")
    calls = []

    def fake_vote(batch: dict[str, Any], model: str, key: str) -> dict[str, Any]:
        calls.append(key)
        return {"batch_id": batch["batch_id"], "model": model, "status": "success"}

    monkeypatch.setattr(runner, "vote", fake_vote)
    monkeypatch.setattr(sys, "argv", ["realized_edit_panel.py", "--run"])
    runner.main()
    rows = [json.loads(line) for line in runner.RESULTS.read_text().splitlines()]
    rows[0]["status"] = "invalid_or_transport_error"
    runner.RESULTS.write_text("".join(json.dumps(row) + "\n" for row in rows))
    calls.clear()
    monkeypatch.setattr(sys, "argv", ["realized_edit_panel.py", "--run", "--resume"])
    runner.main()
    assert calls == ["fake-test-key"]


@pytest.mark.parametrize("missing_family", [False, True])
def test_public_bundle_recomputes_dissent_without_private_ledger(
    panel: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    missing_family: bool,
) -> None:
    summary = importlib.import_module("summarize_realized_edit_panel")
    pair = {
        "mutation_id": "mut-a",
        "operator": "edit",
        "report_a": "a",
        "report_b": "b",
    }
    monkeypatch.setattr(summary, "load_pairs", lambda: [pair])
    digest = hashlib.sha256(json.dumps({"report_a": "a", "report_b": "b"}, sort_keys=True).encode())
    protocol = {
        "model_ids": list(summary.MODELS),
        "input_sha256": {"mut-a": digest.hexdigest()},
        "request_accounting": {"physical_requests": 3, "physical_request_status": {"success": 3}},
    }
    (tmp_path / "protocol.json").write_text(json.dumps(protocol))
    rows = [
        {
            "mutation_id": "mut-a",
            "model": model,
            "status": "success",
            "vote": {
                "quality_changed": "yes" if index < 2 else "no",
                "action_changed": "no" if index < 2 else "uncertain",
                "quality_reason": "Changed clarity",
                "action_reason": "Verification remains possible",
            },
        }
        for index, model in enumerate(summary.MODELS)
    ]
    if missing_family:
        rows[-1] = {"mutation_id": "mut-a", "model": summary.MODELS[-1], "status": "http_error"}
    (tmp_path / "annotations.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    monkeypatch.setattr(
        sys, "argv", ["summarize_realized_edit_panel.py", "--bundle", str(tmp_path)]
    )
    summary.main()
    result = json.loads(capsys.readouterr().out)
    assert result["majority_categories"] == {"incomplete" if missing_family else "quality_only": 1}
    assert result["pairs_with_any_dissent"] == (0 if missing_family else 1)
    assert result["successful_votes"] == (2 if missing_family else 3)
