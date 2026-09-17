"""E3b: materialization outcome ledger (written/no_op/duplicate/safety/error)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import sloplab.mutations.materialize as materialize_module
from sloplab.corpus.loader import discover_fixtures
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import (
    check_materialization,
    materialize_suite,
    read_materialization_ledger,
)
from tests._helpers import write_canonical_fixture


def _workspace(tmp_path: Path) -> dict[str, Any]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Ledger clean report",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "b-000",
        fixture_id="canonical-b-000",
        title="Ledger second report",
        report_class="valid",
    )
    suite = {
        "name": "ledger-suite",
        "base_seed": 21,
        "corpus_root": str(corpus),
        "include_canonical_cases": True,
        "policies": {
            "valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]},
        },
    }
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(yaml.safe_dump(suite), encoding="utf-8")
    suite_config = SuiteConfig.model_validate(
        yaml.safe_load(suite_path.read_text(encoding="utf-8"))
    )
    canonical, _ = discover_fixtures(corpus)
    return {"corpus": corpus, "suite_config": suite_config, "canonical": canonical}


def _tallies(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"written": 0, "no_op": 0, "duplicate": 0, "safety_blocked": 0, "error": 0}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return counts


def test_clean_run_records_every_plan_once(tmp_path: Path) -> None:
    paths = _workspace(tmp_path)
    result = materialize_suite(paths["suite_config"], paths["canonical"], tmp_path / "out")
    header, rows = read_materialization_ledger(tmp_path / "out")
    assert header["planned"] == len(rows) > 0
    assert _tallies(rows) == {
        "written": header["written"],
        "no_op": 0,
        "duplicate": 0,
        "safety_blocked": 0,
        "error": 0,
    }
    assert header["planned"] == header["written"]
    assert result.cases_written == header["written"]
    assert "planned" in result.summary()
    reconciled = check_materialization(tmp_path / "out")
    assert reconciled["planned"] == reconciled["written"] == reconciled["selected"] - 2
    assert reconciled["canonical_included"] == 2


def test_duplicate_plans_are_visible_not_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_plan_suite = materialize_module.plan_suite

    def _doubled(config: Any, fixtures: Any) -> Any:
        plans, counts = real_plan_suite(config, fixtures)
        return ([*plans, plans[0]], counts)

    monkeypatch.setattr(materialize_module, "plan_suite", _doubled)
    paths = _workspace(tmp_path)
    result = materialize_suite(paths["suite_config"], paths["canonical"], tmp_path / "out")
    header, rows = read_materialization_ledger(tmp_path / "out")
    assert header["planned"] == len(rows) == len(result.outcomes)
    assert header["duplicate"] == 1
    dupes = [r for r in rows if r["status"] == "duplicate"]
    assert len(dupes) == 1 and dupes[0]["detail"] == "duplicate case id"
    assert check_materialization(tmp_path / "out")["written"] == header["written"]


def test_no_op_note_and_clone_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _IdleOperator:
        def apply(self, report: Any, rng: Any) -> Any:
            _ = (report, rng)
            return report.raw_text, {"note": "test double idle"}

    class _CloneOperator:
        def apply(self, report: Any, rng: Any) -> Any:
            _ = rng
            return report.raw_text, {}

    paths = _workspace(tmp_path)
    monkeypatch.setattr(materialize_module, "get_operator", lambda name: _IdleOperator())
    result = materialize_suite(paths["suite_config"], paths["canonical"], tmp_path / "out-idle")
    header, rows = read_materialization_ledger(tmp_path / "out-idle")
    assert header["no_op"] == header["planned"] > 0
    assert all(r["detail"] == "test double idle" for r in rows)
    assert result.cases_written == 0

    monkeypatch.setattr(materialize_module, "get_operator", lambda name: _CloneOperator())
    materialize_suite(paths["suite_config"], paths["canonical"], tmp_path / "out-clone")
    header2, rows2 = read_materialization_ledger(tmp_path / "out-clone")
    assert header2["no_op"] == header2["planned"] > 0
    assert all(r["detail"] == "no textual change" for r in rows2)


def test_safety_blocked_is_recorded_without_raw_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _workspace(tmp_path)
    monkeypatch.setattr(
        materialize_module,
        "validate_content_safety",
        lambda text: ["non-reserved CVE reference (only CVE-2099-* allowed): CVE-2024-0001"],
    )
    result = materialize_suite(paths["suite_config"], paths["canonical"], tmp_path / "out")
    header, rows = read_materialization_ledger(tmp_path / "out")
    assert header["safety_blocked"] == header["planned"] > 0
    assert result.cases_written == 0
    assert len(result.safety_violations) == header["planned"]
    for row in rows:
        assert "CVE-2024-0001" not in row["detail"]
        assert row["detail"] == "1 violation(s) blocked"
    assert list((tmp_path / "out" / "adversarial").rglob("report.md")) == []


def test_plan_errors_are_isolated_not_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _BoomOperator:
        def apply(self, report: Any, rng: Any) -> Any:
            _ = (report, rng)
            raise RuntimeError("simulated operator failure")

    paths = _workspace(tmp_path)
    monkeypatch.setattr(materialize_module, "get_operator", lambda name: _BoomOperator())
    result = materialize_suite(paths["suite_config"], paths["canonical"], tmp_path / "out")
    assert result.cases_written == 0
    header, rows = read_materialization_ledger(tmp_path / "out")
    assert header["error"] == header["planned"] > 0
    assert all(r["detail"] == "RuntimeError in apply" for r in rows)
    assert "simulated operator failure" not in json.dumps(rows)
    # The run still publishes its (empty) index + ledger: loss is visible.
    assert (tmp_path / "out" / "suite-index.jsonl").is_file()
    reconciled = check_materialization(tmp_path / "out")
    assert reconciled["written"] == 0

    def _missing_operator(name: str) -> Any:
        raise KeyError(f"unknown operator {name!r}")

    monkeypatch.setattr(materialize_module, "get_operator", _missing_operator)
    materialize_suite(paths["suite_config"], paths["canonical"], tmp_path / "out2")
    _, rows2 = read_materialization_ledger(tmp_path / "out2")
    assert all(r["detail"] == "KeyError in resolve-operator" for r in rows2)


def test_dropped_ledger_row_breaks_reconciliation(tmp_path: Path) -> None:
    paths = _workspace(tmp_path)
    materialize_suite(paths["suite_config"], paths["canonical"], tmp_path / "out")
    ledger = tmp_path / "out" / "materialization-ledger.jsonl"
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 2
    ledger.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="planned"):
        read_materialization_ledger(tmp_path / "out")


def test_index_ledger_mismatch_is_visible(tmp_path: Path) -> None:
    paths = _workspace(tmp_path)
    materialize_suite(paths["suite_config"], paths["canonical"], tmp_path / "out")
    index = tmp_path / "out" / "suite-index.jsonl"
    lines = index.read_text(encoding="utf-8").splitlines()
    mutated = [line for line in lines[1:] if '"mutated"' in line]
    assert mutated
    index.write_text(
        lines[0] + "\n" + "\n".join(line for line in lines[1:] if line != mutated[0]) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="do not match"):
        check_materialization(tmp_path / "out")


def test_unknown_status_rejected(tmp_path: Path) -> None:
    paths = _workspace(tmp_path)
    materialize_suite(paths["suite_config"], paths["canonical"], tmp_path / "out")
    ledger = tmp_path / "out" / "materialization-ledger.jsonl"
    text = ledger.read_text(encoding="utf-8").replace("materialization_outcome", "mystery", 1)
    ledger.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="malformed|unknown"):
        read_materialization_ledger(tmp_path / "out")
