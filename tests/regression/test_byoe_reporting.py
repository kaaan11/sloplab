"""End-to-end external evaluation, persisted failures and offline rendering."""

from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.models.run import RunMetadata
from sloplab.reporting.html import write_html_report
from sloplab.reporting.outcomes import OUTCOMES_HASH_KEY, OutcomeLedgerError, read_failure_outcomes
from sloplab.reporting.writers import read_run_jsonl
from tests._byoe_helpers import evaluator_file, tiny_suite


@pytest.mark.parametrize("selection", ["external", "built-in", "both"])
def test_benchmark_and_evaluate_sources(tmp_path: Path, selection: str) -> None:
    suite = tiny_suite(tmp_path)
    module = evaluator_file(tmp_path)
    options: list[str] = []
    if selection in ("built-in", "both"):
        options += ["--evaluator", "rules-baseline"]
    if selection in ("external", "both"):
        options += ["--evaluator-module", f"{module}:make"]
    out, evaluated = tmp_path / "out", tmp_path / "evaluated"
    runner = CliRunner()
    for command in [
        ["benchmark", str(suite), *options, "--out", str(out)],
        ["evaluate", str(out), *options, "--out", str(evaluated)],
    ]:
        result = runner.invoke(cli, command)
        assert result.exit_code == 0, result.output
    for root in (out, evaluated):
        meta, records = read_run_jsonl(root / "run.jsonl")
        assert meta is not None
        assert {r.evaluator_name for r in records} == {ev.name for ev in meta.evaluators}
        if selection in ("external", "both"):
            assert ("byoe-test", "1.2") in {(ev.name, ev.version) for ev in meta.evaluators}
        assert (root / "outcomes.jsonl").read_bytes() == b""
        report = runner.invoke(cli, ["report", str(root / "run.jsonl"), "--format", "html"])
        assert report.exit_code == 0, report.output
        assert (root / "report.html").is_file()


@pytest.mark.parametrize("options", [[], ["--evaluator-module", "absent.py:make"]])
def test_bad_selection_rejected_before_output(tmp_path: Path, options: list[str]) -> None:
    suite = tiny_suite(tmp_path)
    out = tmp_path / "should-not-exist"
    result = CliRunner().invoke(cli, ["benchmark", str(suite), *options, "--out", str(out)])
    assert result.exit_code != 0
    assert not out.exists()


@pytest.mark.parametrize("all_failed", [False, True])
def test_typed_failure_sidecar_and_all_failed_html(tmp_path: Path, all_failed: bool) -> None:
    suite = tiny_suite(tmp_path)
    extra = """
original = evaluator.evaluate
def evaluate(report, context):
    if ALL_FAILED or 'Medium confidentiality' in report.raw_text:
        raise EvaluationFailure('timeout', 1, 'SECRET_PROMPT', 'SECRET_EXCEPTION')
    return original(report, context)
evaluator.evaluate = evaluate
""".replace("ALL_FAILED", str(all_failed))
    module = evaluator_file(tmp_path, extra)
    out = tmp_path / "out"
    result = CliRunner().invoke(
        cli,
        ["benchmark", str(suite), "--evaluator-module", f"{module}:evaluator", "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert "FAILED-EVAL (timeout)" in result.output
    meta, records = read_run_jsonl(out / "run.jsonl")
    assert meta is not None
    rows = [json.loads(raw) for raw in (out / "outcomes.jsonl").read_text().splitlines()]
    assert rows and all(r["error_kind"] == "timeout" and r["status"] == "failed" for r in rows)
    assert {r.case_id for r in records}.isdisjoint({r["case_id"] for r in rows})
    assert len(records) + len(rows) == 4
    if all_failed:
        assert not records
    else:
        assert records
    expected = hashlib.sha256((out / "outcomes.jsonl").read_bytes()).hexdigest()
    assert meta.suite_config[OUTCOMES_HASH_KEY] == expected
    page = write_html_report(out / "run.jsonl", out / "report.html").read_text()
    assert f"{len(rows)} operational failures" in page
    if all_failed:
        assert "Not available" in page
        assert "0.0%" not in page
    for path in out.glob("*"):
        if path.is_file():
            assert "SECRET_" not in path.read_text()
    assert "SECRET_" not in result.output


def test_unsafe_name_not_used_as_a_path(tmp_path: Path) -> None:
    suite = tiny_suite(tmp_path)
    name = "../../<script>alert(1)</script>"
    module = evaluator_file(tmp_path, f"evaluator.name = {name!r}\n")
    out = tmp_path / "out"
    result = CliRunner().invoke(
        cli,
        ["benchmark", str(suite), "--evaluator-module", f"{module}:evaluator", "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    metrics = list(out.glob("metrics-*.json"))
    assert len(metrics) == 1 and metrics[0].name.startswith("metrics-sha256-")
    assert json.loads(metrics[0].read_text())["evaluator_name"] == name
    page = write_html_report(out / "run.jsonl", out / "report.html").read_text()
    assert "<script" not in page
    assert "&lt;script&gt;" in page


def test_offline_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("network forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    suite, module = tiny_suite(tmp_path), evaluator_file(tmp_path)
    out = tmp_path / "out"
    runner = CliRunner()
    assert (
        runner.invoke(
            cli,
            [
                "benchmark",
                str(suite),
                "--evaluator",
                "rules-baseline",
                "--evaluator-module",
                f"{module}:make",
                "--out",
                str(out),
            ],
        ).exit_code
        == 0
    )
    assert runner.invoke(cli, ["report", str(out / "run.jsonl"), "--format", "html"]).exit_code == 0


def test_missing_or_wrong_bound_sidecar_fails_closed(tmp_path: Path) -> None:
    from tests._byoe_helpers import metadata

    meta = metadata("test-eval")
    meta.suite_config[OUTCOMES_HASH_KEY] = hashlib.sha256(b"").hexdigest()
    path = tmp_path / "run.jsonl"
    with pytest.raises(OutcomeLedgerError, match="Missing outcomes"):
        read_failure_outcomes(path, meta, [])
    (tmp_path / "outcomes.jsonl").write_text("garbage")
    with pytest.raises(OutcomeLedgerError, match="hash mismatch"):
        read_failure_outcomes(path, meta, [])


@pytest.mark.parametrize(
    "payload, message",
    [
        ("broken", "Invalid outcomes.jsonl JSON"),
        ("[]", "schema"),
        ('{"schema_version":2}', "schema"),
        ('{"schema_version":1}', "identity/status"),
    ],
)
def test_malformed_legacy_outcomes(tmp_path: Path, payload: str, message: str) -> None:
    (tmp_path / "outcomes.jsonl").write_text(payload)
    with pytest.raises(OutcomeLedgerError, match=message):
        read_failure_outcomes(tmp_path / "run.jsonl", None, [])


def test_duplicate_conflicting_and_unknown_evaluator_outcomes(tmp_path: Path) -> None:
    from tests._byoe_helpers import metadata
    from tests.unit.test_scoring import record

    row = {
        "schema_version": 1,
        "case_id": "x",
        "evaluator_name": "test-eval",
        "status": "failed",
        "error_kind": "timeout",
    }
    ledger = tmp_path / "outcomes.jsonl"
    meta: RunMetadata = metadata("test-eval")
    ledger.write_text(json.dumps(row) + "\n" + json.dumps(row))
    with pytest.raises(OutcomeLedgerError, match="Duplicate"):
        read_failure_outcomes(tmp_path / "run.jsonl", meta, [])
    ledger.write_text(json.dumps(row))
    with pytest.raises(OutcomeLedgerError, match="conflicts"):
        read_failure_outcomes(tmp_path / "run.jsonl", meta, [record("x")])
    with pytest.raises(OutcomeLedgerError, match="absent from run metadata"):
        read_failure_outcomes(tmp_path / "run.jsonl", metadata("other"), [])


def test_failure_order_and_sensitive_kind(tmp_path: Path) -> None:
    from sloplab.evaluators.llm.failures import EvaluationFailure
    from sloplab.reporting.outcomes import write_failure_outcomes
    from sloplab.scoring.harness import CaseOutcome

    outcomes = [
        CaseOutcome(
            case_id=case,
            evaluator_name=name,
            status="failed",
            failure=EvaluationFailure("SECRET_TOKEN", 1, "SECRET_HASH", "SECRET_DETAIL"),
        )
        for name, case in [("z", "c"), ("a", "b"), ("a", "a")]
    ]
    first, second = tmp_path / "a", tmp_path / "b"
    assert write_failure_outcomes(first, outcomes) == write_failure_outcomes(second, outcomes[::-1])
    assert first.read_bytes() == second.read_bytes()
    assert "SECRET" not in first.read_text()
    rows = [json.loads(line) for line in first.read_text().splitlines()]
    assert [(r["evaluator_name"], r["case_id"]) for r in rows] == [
        ("a", "a"),
        ("a", "b"),
        ("z", "c"),
    ]
    assert all(r["error_kind"] == "unknown" for r in rows)


def test_metrics_paths_are_unique_on_case_insensitive_filesystems() -> None:
    from sloplab.cli.main import _metrics_filename

    names = ["example", "Example", "EXAMPLE", "sha256-abc", "../../invalid", "<script>"]
    paths = [_metrics_filename(name) for name in names]
    assert len(paths) == len({path.lower() for path in paths})
    assert all("/" not in path and "\\" not in path for path in paths)
