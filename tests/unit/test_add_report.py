"""Schema reuse, parser reuse and Click integration for canonical creation."""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner
from pydantic import ValidationError

from sloplab.cli.main import cli
from sloplab.corpus.add_report import (
    AddReportError,
    manifest_yaml,
    prepare_add_report,
    read_report,
)
from sloplab.corpus.loader import discover_fixtures, load_canonical_fixture
from sloplab.corpus.validation import validate_corpus
from sloplab.models.enums import DIMENSIONS, ImpactClass, ReportClass, canonical_expected_decision
from sloplab.models.manifest import CanonicalManifest, GroundTruth
from tests._add_report_helpers import (
    REPORT,
    answers,
    make_corpus,
    make_manifest,
    make_source,
    snapshot,
)


def test_h1_uses_parser_and_ignores_fenced_headings(tmp_path: Path) -> None:
    source = make_source(tmp_path, b"```python\n# Not the title\n```\n# Actual title\n")
    assert source.title == "Actual title"


@pytest.mark.parametrize("body", [b"No title", b"## Not H1", b"```\n# Fake\n```"])
def test_missing_h1_is_actionable(tmp_path: Path, body: bytes) -> None:
    with pytest.raises(AddReportError, match="no H1"):
        make_source(tmp_path, body)


@pytest.mark.parametrize("kind", ["missing", "directory", "invalid-utf8"])
def test_bad_source(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "input.md"
    if kind == "directory":
        path.mkdir()
    elif kind == "invalid-utf8":
        path.write_bytes(b"\xff\xfe")
    with pytest.raises(AddReportError):
        read_report(path)


@pytest.mark.parametrize(
    "slug",
    ["", "../escape", "/absolute", "Uppercase", "bad_name", "trailing-", "a\\b", "a\nb", ".hidden"],
)
def test_invalid_slug_uses_manifest_schema(tmp_path: Path, slug: str) -> None:
    with pytest.raises(AddReportError, match="invalid manifest"):
        make_manifest(make_source(tmp_path), slug=slug)


@pytest.mark.parametrize("report_class", list(ReportClass))
def test_class_mapping_and_yaml_roundtrip(tmp_path: Path, report_class: ReportClass) -> None:
    manifest = make_manifest(make_source(tmp_path), report_class=report_class)
    assert manifest.id == "canonical-new-001"
    assert manifest.expected_decision() == canonical_expected_decision(report_class)
    text = manifest_yaml(manifest)
    assert manifest_yaml(manifest) == text
    assert CanonicalManifest.model_validate(yaml.safe_load(text)) == manifest
    assert "!!python" not in text
    assert "pair_id:" not in text


@pytest.mark.parametrize("impact", list(ImpactClass))
def test_impact_values_are_existing_enum(tmp_path: Path, impact: ImpactClass) -> None:
    manifest = make_manifest(make_source(tmp_path), ground_truth=GroundTruth(impact_class=impact))
    assert manifest.ground_truth.impact_class == impact


def test_unknown_enums_rejected_by_existing_models(tmp_path: Path) -> None:
    data = make_manifest(make_source(tmp_path)).model_dump(mode="json")
    data["report_class"] = "maybe"
    with pytest.raises(ValidationError):
        CanonicalManifest.model_validate(data)
    with pytest.raises(ValidationError):
        GroundTruth.model_validate({"impact_class": "catastrophic"})


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf"), -float("inf")])
def test_mutated_dimension_dict_is_revalidated(tmp_path: Path, value: float) -> None:
    ground_truth = GroundTruth(expected_dimensions={DIMENSIONS[0]: 0.5})
    ground_truth.expected_dimensions[DIMENSIONS[0]] = value
    with pytest.raises(AddReportError, match="dimension"):
        make_manifest(make_source(tmp_path), ground_truth=ground_truth)


def test_unknown_dimension_reuses_schema(tmp_path: Path) -> None:
    ground_truth = GroundTruth()
    ground_truth.expected_dimensions["made_up"] = 0.9
    with pytest.raises(AddReportError, match="unknown dimension"):
        make_manifest(make_source(tmp_path), ground_truth=ground_truth)


def test_stage_loads_and_preview_is_detached(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    before = snapshot(root)
    with prepare_add_report(source, make_manifest(source), root) as prepared:
        assert not prepared.staged_directory.is_relative_to(root)
        loaded = load_canonical_fixture(
            prepared.staged_directory, prepared.staged_directory.parents[1]
        )
        assert loaded.manifest.title == source.title
        prepared.manifest.ground_truth.expected_dimensions[DIMENSIONS[0]] = 0.0
        assert prepared.manifest.ground_truth.expected_dimensions[DIMENSIONS[0]] == 0.9
        assert prepared.fixture_validation.ok and prepared.preflight.ok
        assert prepared.preflight.checked_canonical == 2
        assert snapshot(root) == before
    assert not prepared.staged_directory.exists()
    assert snapshot(root) == before


def test_warnings_are_real_and_not_errors(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    manifest = make_manifest(source, ground_truth=GroundTruth(reproducible=None))
    with prepare_add_report(source, manifest, root) as prepared:
        assert prepared.preflight.ok
        assert any("reproducible" in w.message for w in prepared.preflight.warnings)


def test_cli_success_is_offline_and_uses_no_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("network/subprocess is forbidden in add-report")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    result = CliRunner().invoke(
        cli, ["add-report", str(source.path), "--corpus", str(root)], input=answers()
    )
    assert result.exit_code == 0, result.output
    assert "Fixture added: canonical-new-001" in result.output
    assert "1 -> 2" in result.output
    assert "sloplab benchmark" in result.output
    assert "dataset-card.md" in result.output
    assert (
        result.output.index("Manifest preview")
        < result.output.index("Confirm this report")
        < result.output.index("Fixture added")
    )
    assert source.path.read_bytes() == source.content
    canonical, derived = discover_fixtures(root)
    assert validate_corpus(canonical, derived, root).ok


@pytest.mark.parametrize("confirmation,exit_code", [("n", 0), (None, 1)])
def test_cli_cancel_and_eof_do_not_write(
    tmp_path: Path, confirmation: str | None, exit_code: int
) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    before = snapshot(root)
    result = CliRunner().invoke(
        cli,
        ["add-report", str(source.path), "--corpus", str(root)],
        input=answers(confirm=confirmation),
    )
    # Click <8.2's CliRunner maps EOF to an empty answer. Exercise actual EOF
    # in a real process below; both runner behaviours must preserve the corpus.
    assert result.exit_code in ({0, 1} if confirmation is None else {exit_code}), result.output
    assert "Fixture added" not in result.output
    assert snapshot(root) == before
    assert not list(tmp_path.glob(".sloplab-stage-*"))


def test_cli_reprompts_bad_slug_and_nonfinite_score(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    inputs = answers(slug="BAD\nnew-001").replace("0.9\n", "nan\n2\n0.9\n", 1)
    result = CliRunner().invoke(
        cli, ["add-report", str(source.path), "--corpus", str(root)], input=inputs
    )
    assert result.exit_code == 0, result.output
    assert "invalid manifest" in result.output
    assert "finite score" in result.output
    assert "Fixture added" in result.output


def test_cli_missing_title_writes_nothing(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    report = tmp_path / "bad.md"
    report.write_text("## Not a title")
    result = CliRunner().invoke(cli, ["add-report", str(report), "--corpus", str(root)])
    assert result.exit_code != 0 and "no H1" in result.output
    assert snapshot(root) == before


def test_cli_invalid_dimension_then_eof_writes_nothing(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)
    inputs = answers().split("0.9", 1)[0] + "2\n"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sloplab.cli.main",
            "add-report",
            str(source.path),
            "--corpus",
            str(root),
        ],
        input=inputs,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0, result.stdout
    assert snapshot(root) == before


def test_actual_eof_at_confirmation_cleans_stage(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sloplab.cli.main",
            "add-report",
            str(source.path),
            "--corpus",
            str(root),
        ],
        input=answers(confirm=None),
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0, result.stdout
    assert "Fixture added" not in result.stdout
    assert snapshot(root) == before
    assert not list(tmp_path.glob(".sloplab-stage-*"))


def test_cli_without_ui_dependency_and_default_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    make_corpus(tmp_path)
    report = tmp_path / "input.md"
    report.write_text(REPORT)
    result = CliRunner().invoke(cli, ["add-report", "input.md"], input=answers())
    assert result.exit_code == 0, result.output
    assert "Fixture added" in result.output


def test_short_h1_fails_once_instead_of_reprompting_slug(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path, b"# A\n")
    before = snapshot(root)
    result = CliRunner().invoke(cli, ["add-report", str(source.path), "--corpus", str(root)])
    assert result.exit_code != 0
    assert "title" in result.output
    assert "Fixture slug:" not in result.output
    assert snapshot(root) == before
