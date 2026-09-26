"""Offline HTML: real helpers, safe text, stable bytes and backward compatibility."""

from __future__ import annotations

import json
import shutil
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.reporting.html import BOOTSTRAP_RESAMPLES, render_html, write_html_report
from sloplab.reporting.outcomes import FailureLedger, FailureRow
from sloplab.reporting.writers import read_run_jsonl, write_run_jsonl
from sloplab.scoring.comparison import bootstrap_accuracy_ci
from tests._byoe_helpers import metadata
from tests.unit.test_scoring import record

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "benchmarks/results/v1-core-example/run.jsonl"
GOLDEN = ROOT / "tests/golden/offline-reference.html"


class Markup(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.attrs: list[tuple[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        self.attrs.extend(attrs)


def test_reference_golden_and_determinism(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = write_html_report(REFERENCE, tmp_path / "first.html").read_bytes()
    assert first == GOLDEN.read_bytes()
    relocated = tmp_path / "relocated"
    relocated.mkdir()
    shutil.copyfile(REFERENCE, relocated / "run.jsonl")
    monkeypatch.chdir(relocated)
    second = write_html_report(relocated / "run.jsonl", tmp_path / "second.html").read_bytes()
    assert first == second
    assert b"/home/kaan" not in first and str(tmp_path).encode() not in first


def test_content_accessibility_and_no_active_resources() -> None:
    page = GOLDEN.read_text()
    for text in (
        "What these numbers are",
        "Authored target agreement",
        "not verified real-world",
        "surface-signature",
        "Evaluator summary",
        "Operator breakdown",
        "Evaluation failures",
        "Run metadata",
        "95% bootstrap CI",
        "False reassurance",
        "Over-rejection",
        "ECE",
        "prefers-color-scheme: dark",
        "overflow-x: auto",
        ":focus-visible",
        "system-ui",
        "Operational failure ledger not available for this legacy run.",
    ):
        assert text in page
    for forbidden in ("<script", "<link", "@import", "url(http"):
        assert forbidden not in page.lower()
    parsed = Markup()
    parsed.feed(page)
    assert "svg" in parsed.tags and "caption" in parsed.tags and "nav" in parsed.tags
    assert not {"img", "iframe", "object", "script", "link"} & set(parsed.tags)
    assert not any(key.startswith("on") or key == "src" for key, _ in parsed.attrs)
    assert 'tabindex="0"' in page


@pytest.mark.parametrize(
    "payload", ["<script>alert(1)</script>", '\"><img src=x onerror=alert(1)>', "& < >"]
)
def test_untrusted_fields_escaped(tmp_path: Path, payload: str) -> None:
    rec = record("child", kind="mutated", parent_id="parent", operator=payload)
    rec.evaluator_name = payload
    rec.evaluator_version = payload
    rec.rationale = payload  # not currently rendered, never unescaped
    meta = metadata(payload)
    meta.evaluators[0].version = payload
    meta.suite_name = payload
    meta.suite_hash = payload
    meta.git_commit = payload
    meta.sloplab_version = payload
    ledger = FailureLedger(True, False, (FailureRow(payload, payload, "timeout"),))
    page = render_html(meta, [rec], ledger)
    assert payload not in page
    assert escape(payload, quote=True) in page
    parsed = Markup()
    parsed.feed(page)
    assert "script" not in parsed.tags and "img" not in parsed.tags
    assert not any(key.startswith("on") for key, _ in parsed.attrs)


def test_summary_reuses_metrics_and_explicit_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    import sloplab.reporting.html as html_module

    records = [record("a"), record("b")]
    meta = metadata("test-eval")
    calls: list[dict[str, Any]] = []

    def checked(rs: Any, **kwargs: Any) -> tuple[float, float, float]:
        calls.append(kwargs)
        return bootstrap_accuracy_ci(rs, **kwargs)

    monkeypatch.setattr(html_module, "bootstrap_accuracy_ci", checked)
    page = render_html(meta, records, FailureLedger(True, True))
    assert calls == [{"resamples": BOOTSTRAP_RESAMPLES, "ci": 0.95, "seed": meta.base_seed}]
    assert "100.0%" in page
    assert "0 operational failures" in page
    assert "2026-01-01T00:00:00+00:00" in page


def test_unscored_case_not_in_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    import sloplab.reporting.html as html_module

    records = [record("scored"), record("unscored", expected=None)]

    def checked(rs: Any, **kwargs: Any) -> tuple[float, float, float]:
        assert len(rs) == 1 and rs[0].case_id == "scored"
        return bootstrap_accuracy_ci(rs, **kwargs)

    monkeypatch.setattr(html_module, "bootstrap_accuracy_ci", checked)
    render_html(metadata("test-eval"), records, FailureLedger(False, False))


def test_no_observations_no_invented_zero_accuracy() -> None:
    page = render_html(metadata("empty"), [], FailureLedger(True, True))
    assert "Not available" in page and "0.0%" not in page


def test_mixed_versions_rejected() -> None:
    rec = record("a")
    rec.evaluator_version = "conflicting"
    with pytest.raises(ValueError, match="version differs"):
        render_html(metadata("test-eval"), [rec], FailureLedger(False, False))


def test_markdown_default_and_explicit_unchanged(tmp_path: Path) -> None:
    runner = CliRunner()
    default, explicit = tmp_path / "default.md", tmp_path / "explicit.md"
    a = runner.invoke(cli, ["report", str(REFERENCE), "--out", str(default)])
    b = runner.invoke(
        cli, ["report", str(REFERENCE), "--format", "markdown", "--out", str(explicit)]
    )
    assert a.exit_code == b.exit_code == 0
    assert a.output == b.output and default.read_bytes() == explicit.read_bytes()


def test_html_analysis_rejected_before_output(tmp_path: Path) -> None:
    analysis = tmp_path / "analysis.json"
    analysis.write_text("{}")
    out = tmp_path / "report.html"
    result = CliRunner().invoke(
        cli,
        [
            "report",
            str(REFERENCE),
            "--format",
            "html",
            "--analysis",
            str(analysis),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code != 0
    assert "HTML reporting currently requires run.jsonl" in result.output
    assert not out.exists()


def test_legacy_failure_sidecar_and_absent_metadata(tmp_path: Path) -> None:
    rec = record("a")
    path = tmp_path / "run.jsonl"
    path.write_text(rec.model_dump_json() + "\n")
    (tmp_path / "outcomes.jsonl").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "case_id": "b",
                "evaluator_name": "test-eval",
                "status": "failed",
                "error_kind": "timeout",
                "adapter_attempts": 1,
                "detail": "SECRET_NOT_RENDERED",
            }
        )
        + "\n"
    )
    page = write_html_report(path, tmp_path / "report.html").read_text()
    assert "legacy, unbound sidecar" in page and "1 operational failures" in page
    assert "SECRET_NOT_RENDERED" not in page
    assert "Not recorded" in page


def test_cannot_overwrite_inputs_and_invalid_records_not_written(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    write_run_jsonl(path, metadata("test-eval"), [record("a")])
    before = path.read_bytes()
    for out in (path, tmp_path / "outcomes.jsonl"):
        with pytest.raises(ValueError, match="must not overwrite"):
            write_html_report(path, out)
    assert path.read_bytes() == before
    meta, records = read_run_jsonl(path)
    assert meta is not None
    records[0].correct = False  # existing metric reader rejects drift
    write_run_jsonl(path, meta, records)
    with pytest.raises(ValueError):
        write_html_report(path, tmp_path / "invalid.html")
    assert not (tmp_path / "invalid.html").exists()


def test_missing_timestamp_does_not_use_model_clock(tmp_path: Path) -> None:
    payload = metadata("test-eval").model_dump(mode="json")
    del payload["started_at"]
    path = tmp_path / "run.jsonl"
    path.write_text(json.dumps(payload) + "\n" + record("a").model_dump_json() + "\n")
    first = write_html_report(path, tmp_path / "a.html").read_bytes()
    second = write_html_report(path, tmp_path / "b.html").read_bytes()
    assert first == second
    assert b"<dt>Recorded timestamp</dt><dd>Not recorded</dd>" in first


def test_html_cannot_modify_completed_bundle(tmp_path: Path) -> None:
    from sloplab.experiments.bundle import KIND_REQUIRED_FILES, begin_publish, finish_publish

    root = tmp_path / "bundle"
    begin_publish(root, kind="study")
    for name in KIND_REQUIRED_FILES["study"]:
        (root / name).write_text("{}")
    write_run_jsonl(root / "run.jsonl", metadata("test-eval"), [record("a")])
    finish_publish(root, kind="study")
    with pytest.raises(ValueError, match="outside the integrity-marked bundle"):
        write_html_report(root / "run.jsonl", root / "report.html")
    assert not (root / "report.html").exists()
    assert write_html_report(root / "run.jsonl", tmp_path / "outside.html").is_file()
