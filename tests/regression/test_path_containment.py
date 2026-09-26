"""Regression coverage for file references that must stay inside their owning root."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from sloplab.corpus.loader import FixtureError, load_canonical_fixture
from sloplab.reporting.analysis import ANALYSIS_SCHEMA_VERSION, AnalysisError, read_versioned_analysis
from sloplab.scoring.harness import build_cases
from tests._helpers import write_canonical_fixture


def _set_report_path(fixture: Path, value: str) -> None:
    manifest_path = fixture / "manifest.yaml"
    document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    document["report"]["path"] = value
    manifest_path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


@pytest.mark.parametrize("kind", ["absolute", "parent"])
def test_manifest_report_path_cannot_escape_corpus(tmp_path: Path, kind: str) -> None:
    root = tmp_path / "corpus"
    fixture = write_canonical_fixture(
        root, "safe", fixture_id="canonical-safe", title="Contained report"
    )
    outside = tmp_path / "outside.md"
    outside.write_text("# Contained report\n", encoding="utf-8")
    value = str(outside) if kind == "absolute" else "../outside.md"
    _set_report_path(fixture, value)

    with pytest.raises(FixtureError, match="must be relative|escapes root"):
        load_canonical_fixture(fixture, root)


def test_manifest_report_symlink_cannot_escape_corpus(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    fixture = write_canonical_fixture(
        root, "safe", fixture_id="canonical-safe", title="Contained report"
    )
    outside = tmp_path / "outside.md"
    outside.write_text("# Contained report\n", encoding="utf-8")
    link = fixture / "outside-link.md"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    _set_report_path(fixture, "canonical/safe/outside-link.md")

    with pytest.raises(FixtureError, match="escapes root"):
        load_canonical_fixture(fixture, root)


def _write_index(path: Path, manifest_path: str) -> None:
    path.write_text(
        json.dumps({"record_type": "suite_header"})
        + "\n"
        + json.dumps(
            {
                "record_type": "suite_case",
                "kind": "mutated",
                "case_id": "mut-outside",
                "manifest_path": manifest_path,
                "report_class": "valid",
            }
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("kind", ["absolute", "parent"])
def test_suite_index_manifest_path_cannot_escape_materialized_root(
    tmp_path: Path, kind: str
) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    materialized = tmp_path / "materialized"
    materialized.mkdir()
    outside_dir = tmp_path / "outside-case"
    outside_dir.mkdir()
    outside_manifest = outside_dir / "mutation-manifest.yaml"
    outside_manifest.write_text("not: read\n", encoding="utf-8")
    value = str(outside_manifest) if kind == "absolute" else "../outside-case/mutation-manifest.yaml"
    index = materialized / "suite-index.jsonl"
    _write_index(index, value)

    with pytest.raises(FixtureError, match="must be relative|escapes root"):
        build_cases(index, corpus, materialized)


def test_suite_index_manifest_symlink_cannot_escape_materialized_root(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    materialized = tmp_path / "materialized"
    materialized.mkdir()
    outside_dir = tmp_path / "outside-case"
    outside_dir.mkdir()
    (outside_dir / "mutation-manifest.yaml").write_text("not: read\n", encoding="utf-8")
    link = materialized / "linked"
    try:
        link.symlink_to(outside_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    index = materialized / "suite-index.jsonl"
    _write_index(index, "linked/mutation-manifest.yaml")

    with pytest.raises(FixtureError, match="escapes root"):
        build_cases(index, corpus, materialized)


def _analysis_document(
    records_path: str, records_file: Path, *, outcomes: dict[str, Any]
) -> dict[str, Any]:
    return {
        "analysis_schema": ANALYSIS_SCHEMA_VERSION,
        "analysis_version": 1,
        "kind": "study",
        "records_path": records_path,
        "records_sha256": hashlib.sha256(records_file.read_bytes()).hexdigest(),
        "records_count": 1,
        "outcomes": outcomes,
        "evaluators": ["ev"],
        "coverage": {"ev": {"planned": 1, "scored": 1, "failed": 0, "not_run": 0}},
        "bundles": {"ev": {}},
    }


@pytest.mark.parametrize("kind", ["absolute", "parent"])
def test_analysis_records_path_cannot_escape_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    outside = tmp_path / "outside.jsonl"
    outside.write_text('{"evaluator_name":"ev","case_id":"c1"}\n', encoding="utf-8")
    value = str(outside) if kind == "absolute" else "../outside.jsonl"
    analysis = bundle / "analysis-v1.json"
    analysis.write_text(
        json.dumps(
            _analysis_document(
                value,
                outside,
                outcomes={"present": False, "path": None, "sha256": None, "lines": 0},
            )
        ),
        encoding="utf-8",
    )
    import sloplab.experiments.bundle as bundle_module

    monkeypatch.setattr(bundle_module, "open_result_dir", lambda *_args, **_kwargs: "complete")
    with pytest.raises(AnalysisError, match="must be relative|escapes root"):
        read_versioned_analysis(analysis)


def test_analysis_records_symlink_cannot_escape_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    outside = tmp_path / "outside.jsonl"
    outside.write_text('{"evaluator_name":"ev","case_id":"c1"}\n', encoding="utf-8")
    link = bundle / "records.jsonl"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    analysis = bundle / "analysis-v1.json"
    analysis.write_text(
        json.dumps(
            _analysis_document(
                "records.jsonl",
                outside,
                outcomes={"present": False, "path": None, "sha256": None, "lines": 0},
            )
        ),
        encoding="utf-8",
    )
    import sloplab.experiments.bundle as bundle_module

    monkeypatch.setattr(bundle_module, "open_result_dir", lambda *_args, **_kwargs: "complete")
    with pytest.raises(AnalysisError, match="escapes root"):
        read_versioned_analysis(analysis)


@pytest.mark.parametrize("kind", ["absolute", "parent"])
def test_analysis_outcomes_path_cannot_escape_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    records = bundle / "records.jsonl"
    records.write_text('{"evaluator_name":"ev","case_id":"c1"}\n', encoding="utf-8")
    outside = tmp_path / "outcomes.jsonl"
    outside.write_text("", encoding="utf-8")
    value = str(outside) if kind == "absolute" else "../outcomes.jsonl"
    analysis = bundle / "analysis-v1.json"
    analysis.write_text(
        json.dumps(
            _analysis_document(
                "records.jsonl",
                records,
                outcomes={
                    "present": True,
                    "path": value,
                    "sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
                    "lines": 0,
                },
            )
        ),
        encoding="utf-8",
    )
    import sloplab.experiments.bundle as bundle_module

    monkeypatch.setattr(bundle_module, "open_result_dir", lambda *_args, **_kwargs: "complete")
    with pytest.raises(AnalysisError, match="must be relative|escapes root"):
        read_versioned_analysis(analysis)


def test_analysis_outcomes_symlink_cannot_escape_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    records = bundle / "records.jsonl"
    records.write_text('{"evaluator_name":"ev","case_id":"c1"}\n', encoding="utf-8")
    outside = tmp_path / "outcomes.jsonl"
    outside.write_text("", encoding="utf-8")
    link = bundle / "outcomes.jsonl"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    analysis = bundle / "analysis-v1.json"
    analysis.write_text(
        json.dumps(
            _analysis_document(
                "records.jsonl",
                records,
                outcomes={
                    "present": True,
                    "path": "outcomes.jsonl",
                    "sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
                    "lines": 0,
                },
            )
        ),
        encoding="utf-8",
    )
    import sloplab.experiments.bundle as bundle_module

    monkeypatch.setattr(bundle_module, "open_result_dir", lambda *_args, **_kwargs: "complete")
    with pytest.raises(AnalysisError, match="escapes root"):
        read_versioned_analysis(analysis)
