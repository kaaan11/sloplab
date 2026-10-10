"""Offline transport and archive checks for the fresh mutation repeat study."""

from __future__ import annotations

import copy
import importlib
import json
import shutil
import urllib.error
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

from sloplab.evaluators.llm.adapter import LLMResponse
from sloplab.evaluators.llm.failures import BudgetExhausted, DeadlineExceeded
from sloplab.experiments.bundle import write_completion
from tests.unit.test_llm_pilot import VALID_PAYLOAD

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def modules(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any]:
    monkeypatch.syspath_prepend(str(ROOT / "experiments/scripts"))
    return (
        importlib.import_module("nemotron_mutation_repeats"),
        importlib.import_module("verify_nemotron_mutation_repeats"),
    )


def routes() -> dict[str, Any]:
    entry = {
        "pricing": {"prompt": "0", "completion": "0", "request": "0"},
        "supported_parameters": ["response_format", "structured_outputs"],
    }
    return {
        "catalog": dict(entry, id="nvidia/nemotron-3-super-120b-a12b:free"),
        "endpoints": [copy.deepcopy(entry)],
    }


class FakeHTTP:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls = 0
        self.error = error

    def set_deadline(self, deadline: float | None) -> None:
        pass

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        if self.error:
            raise self.error
        return LLMResponse(text=VALID_PAYLOAD, latency_ms=1)


def prepare(module: Any, archive: Path) -> dict[str, Any]:
    archive.mkdir()
    protocol: dict[str, Any] = module.make_protocol(ROOT)
    module.write_new(archive / "protocol.json", protocol)
    return protocol


def fast_clock(monkeypatch: pytest.MonkeyPatch, runner: Any) -> None:
    now = [1000.0]
    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(runner.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))


def test_exact_plan_and_reject_budget_or_identity_tampering(modules: tuple[Any, Any]) -> None:
    runner, verifier = modules
    protocol = runner.make_protocol(ROOT)
    verifier.validate_protocol(ROOT, protocol)
    keys = [(case, b["repeat_index"]) for b in protocol["batches"] for case in b["case_ids"]]
    assert len(keys) == len(set(keys)) == 891
    assert len(protocol["batches"]) == 90
    for mutation in ("budget", "repeat", "identity", "retry", "source"):
        changed = copy.deepcopy(protocol)
        if mutation == "budget":
            changed["max_requests"] = 892
        elif mutation == "repeat":
            changed["batches"][30]["repeat_index"] = 0
        elif mutation == "identity":
            changed["input_identity"] = {}
        elif mutation == "retry":
            changed["batches"][0]["config"]["budget"]["max_retries_per_case"] = 1
        else:
            changed["source_sha256"].pop(next(iter(changed["source_sha256"])))
        with pytest.raises(ValueError):
            verifier.validate_protocol(ROOT, changed)


@pytest.mark.parametrize("code", [401, 402, 403, 404, 429])
def test_stop_prevents_later_physical_calls(modules: tuple[Any, Any], code: int) -> None:
    runner, _ = modules
    http = FakeHTTP(urllib.error.HTTPError("https://example.org", code, "blocked", Message(), None))
    transport = runner.StudyTransport(http, interval=0)
    with pytest.raises(urllib.error.HTTPError):
        transport.complete("test")
    with pytest.raises(BudgetExhausted):
        transport.complete("test")
    assert http.calls == transport.started == 1
    assert transport.stop_reason == f"http.{code}"


def test_global_cap_survives_batch_deadline_resets(modules: tuple[Any, Any]) -> None:
    runner, _ = modules
    http = FakeHTTP()
    transport = runner.StudyTransport(http, cap=2, interval=0)
    for _ in range(2):
        transport.set_deadline(None)
        transport.complete("test")
    transport.set_deadline(None)
    with pytest.raises(BudgetExhausted):
        transport.complete("test")
    assert http.calls == transport.started == 2


def test_cross_batch_pacing_refuses_without_dispatch(
    modules: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, _ = modules
    fast_clock(monkeypatch, runner)
    http = FakeHTTP()
    transport = runner.StudyTransport(http)
    transport.complete("first")
    transport.set_deadline(1001.0)
    with pytest.raises(DeadlineExceeded):
        transport.complete("next batch")
    assert http.calls == transport.started == 1
    transport.set_deadline(1010.0)
    transport.complete("next batch")
    assert runner.time.monotonic() == 1003.1


@pytest.mark.parametrize("change", ["price", "nan", "missing", "schema"])
def test_route_gate_fails_closed(modules: tuple[Any, Any], change: str) -> None:
    runner, _ = modules
    route = routes()
    if change == "price":
        route["endpoints"][0]["pricing"]["request"] = "0.01"
    elif change == "nan":
        route["catalog"]["pricing"]["prompt"] = "NaN"
    elif change == "missing":
        route["endpoints"][0]["pricing"].pop("completion")
    else:
        route["endpoints"][0]["supported_parameters"] = []
    with pytest.raises(ValueError):
        runner.validate_routes(route["catalog"], route["endpoints"])


@pytest.mark.parametrize("change", ["no_pricing", "null_price", "text_price"])
def test_verifier_route_check_raises_value_error_on_malformed_pricing(
    modules: tuple[Any, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    runner, verifier = modules
    fast_clock(monkeypatch, runner)
    archive = tmp_path / "study"
    protocol = prepare(runner, archive)
    runner.execute(ROOT, archive, protocol, runner.StudyTransport(FakeHTTP()), routes)
    target = tmp_path / "tampered"
    shutil.copytree(archive, target)
    route_path = target / "r0-b01-route.json"
    route = json.loads(route_path.read_text())
    if change == "no_pricing":
        del route["endpoints"][0]["pricing"]
    elif change == "null_price":
        route["catalog"]["pricing"]["prompt"] = None
    else:
        route["catalog"]["pricing"]["prompt"] = "free"
    route_path.write_text(json.dumps(route))
    with pytest.raises(ValueError, match="Missing prices|Nonzero route price"):
        verifier.replay(ROOT, target)


def test_verifier_rejects_duplicate_keys_in_records_and_outcomes(
    modules: tuple[Any, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, verifier = modules
    fast_clock(monkeypatch, runner)
    archive = tmp_path / "study"
    protocol = prepare(runner, archive)
    checks = [0]

    def check() -> dict[str, Any]:
        checks[0] += 1
        if checks[0] > 1:
            raise ValueError("stop after first bundle")
        return routes()

    runner.execute(ROOT, archive, protocol, runner.StudyTransport(FakeHTTP()), check)
    for name in ("records.jsonl", "outcomes.jsonl"):
        target = tmp_path / ("dup-" + name)
        shutil.copytree(archive, target)
        path = target / "r0-b01" / name
        lines = path.read_text().splitlines()
        lines[0] = lines[0][:-1] + ', "case_id": "duplicated"}'
        path.write_text("\n".join(lines) + "\n")
        write_completion(path.parent, kind="llm-pilot")
        with pytest.raises(ValueError, match="Duplicate JSON key"):
            verifier.replay(ROOT, target)


def test_offline_summary_reports_protocol_counts(
    modules: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner, _ = modules
    protocol = runner.make_protocol(ROOT)
    protocol["selected_case_ids"] = protocol["selected_case_ids"][:-1]
    protocol["batches"] = protocol["batches"][:-1]
    monkeypatch.setattr(runner, "make_protocol", lambda _: protocol)
    monkeypatch.setattr("sys.argv", ["nemotron_mutation_repeats.py"])
    monkeypatch.setattr(
        "verify_nemotron_mutation_repeats.validate_protocol", lambda *args, **kwargs: None
    )
    runner.main()
    summary = json.loads(capsys.readouterr().out)
    assert summary["cases"] == 296
    assert summary["batches"] == 89


@pytest.mark.parametrize("reason", ["route", "http"])
def test_stopped_archive_replays_missingness_and_cannot_rerun(
    modules: tuple[Any, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    runner, verifier = modules
    fast_clock(monkeypatch, runner)
    archive = tmp_path / "study"
    protocol = prepare(runner, archive)
    http = FakeHTTP(
        urllib.error.HTTPError("https://example.org", 429, "stop", Message(), None)
        if reason == "http"
        else None
    )
    transport = runner.StudyTransport(http)
    checks = [0]

    def check() -> dict[str, Any]:
        checks[0] += 1
        if reason == "route" and checks[0] == 2:
            bad = routes()
            bad["endpoints"][0]["pricing"]["prompt"] = "1"
            return bad
        return routes()

    summary = runner.execute(ROOT, archive, protocol, transport, check)
    assert summary == verifier.replay(ROOT, archive)
    assert summary["physical_requests"] == (1 if reason == "http" else 10)
    assert summary["valid"] == (0 if reason == "http" else 10)
    assert summary["non_dispatch_failures"] == (9 if reason == "http" else 0)
    assert not summary["full_response_coverage"]
    assert summary["stability"]["mutated"]["complete"] == 0
    assert all(r["metrics"] is None for r in summary["per_repeat"])
    prior = http.calls
    with pytest.raises(FileExistsError):
        runner.execute(ROOT, archive, protocol, transport, check)
    assert http.calls == prior


def test_fresh_same_repeat_parent_pairing_and_incomplete_stability(
    modules: tuple[Any, Any],
) -> None:
    _, verifier = modules
    canonical, mutated = verifier.load_cases(ROOT)
    child = next(
        c
        for c in mutated
        if c.expected_decision
        == next(p for p in canonical if p.case_id == c.parent_id).expected_decision
    )
    parent = next(p for p in canonical if p.case_id == child.parent_id)
    rows = {}
    for r, decision in enumerate(["accept", "reject", "accept"]):
        rows[(child.case_id, r)] = {"decision": decision, "correct": False, "case_kind": "mutated"}
    # A parent in repeat 1 cannot fill the missing parent control in repeat 0 or 2.
    rows[(parent.case_id, 1)] = {"decision": "accept", "correct": True, "case_kind": "canonical"}
    result = verifier.analyze(canonical + mutated, rows)
    assert result["stability"]["mutated"]["changed"] == 1
    assert result["stability"]["canonical"]["complete"] == 0
    assert result["per_repeat"][0]["decision_preserving_drift"]["paired"] == 0
    assert result["per_repeat"][1]["decision_preserving_drift"]["changed"] == 1
    assert result["per_repeat"][2]["decision_preserving_drift"]["paired"] == 0


def test_replay_detects_duplicate_records_even_with_updated_bundle_hashes(
    modules: tuple[Any, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, verifier = modules
    fast_clock(monkeypatch, runner)
    archive = tmp_path / "study"
    protocol = prepare(runner, archive)
    checks = [0]

    def check() -> dict[str, Any]:
        checks[0] += 1
        if checks[0] > 1:
            raise ValueError("stop after first bundle")
        return routes()

    runner.execute(ROOT, archive, protocol, runner.StudyTransport(FakeHTTP()), check)
    target = tmp_path / "tampered"
    shutil.copytree(archive, target)
    records = target / "r0-b01/records.jsonl"
    records.write_text(records.read_text() + records.read_text().splitlines()[0] + "\n")
    write_completion(records.parent, kind="llm-pilot")
    with pytest.raises(ValueError, match="Duplicate records"):
        verifier.replay(ROOT, target)


def test_full_891_mock_requests_replay_three_global_repeats(
    modules: tuple[Any, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, verifier = modules
    fast_clock(monkeypatch, runner)
    archive = tmp_path / "full-study"
    protocol = prepare(runner, archive)
    http = FakeHTTP()
    result = runner.execute(ROOT, archive, protocol, runner.StudyTransport(http), routes)
    assert result["physical_requests"] == result["valid"] == http.calls == 891
    assert result["full_response_coverage"]
    assert result["failed"] == result["not_run"] == 0
    assert result["stability"]["mutated"]["unanimous"] == 237
    assert result["stability"]["canonical"]["unanimous"] == 60
    assert [r["repeat_index"] for r in result["per_repeat"]] == [0, 1, 2]
    assert all(r["metrics"] is not None for r in result["per_repeat"])
    assert all(r["decision_preserving_drift"]["paired"] == 141 for r in result["per_repeat"])
    assert result == verifier.replay(ROOT, archive)


@pytest.mark.parametrize("change", ["leftover", "protocol", "transport"])
def test_execution_rejects_unprepared_state_before_calls(
    modules: tuple[Any, Any], tmp_path: Path, change: str
) -> None:
    runner, _ = modules
    archive = tmp_path / "study"
    protocol = prepare(runner, archive)
    http = FakeHTTP()
    transport = runner.StudyTransport(http)
    if change == "leftover":
        (archive / "r0-b01").mkdir()
    elif change == "protocol":
        changed = copy.deepcopy(protocol)
        changed["prepared_at"] = "changed"
        (archive / "protocol.json").write_text(json.dumps(changed))
    else:
        transport.cap = 892
    with pytest.raises(ValueError):
        runner.execute(ROOT, archive, protocol, transport, routes)
    assert http.calls == 0
    assert not (archive / "execution-started.json").exists()
