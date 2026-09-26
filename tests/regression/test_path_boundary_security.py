"""Issue #17: untrusted repository paths must stay inside their declared roots."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from sloplab.corpus.loader import FixtureError, load_canonical_fixture
from sloplab.experiments.bundle import write_completion
from sloplab.reporting.analysis import AnalysisError, analysis_filename, read_versioned_analysis
from sloplab.scoring.harness import build_cases
from tests._helpers import write_canonical_fixture
from tests.regression.test_versioned_analysis import _published_run


def _escape_path(mode: str, *, root: Path, outside: Path, link_name: str) -> str:
    if mode == "absolute":
        return str(outside.resolve())
    if mode == "parent":
        return str(Path("..") / outside.name)
    link = root / link_name
    link.symlink_to(outside, target_is_directory=outside.is_dir())
    return link_name


@pytest.mark.parametrize("mode", ["absolute", "parent", "symlink"])
def test_canonical_report_path_cannot_escape_corpus(tmp_path: Path, mode: str) -> None:
    corpus = tmp_path / "corpus"
    fixture_dir = write_canonical_fixture(
        corpus,
        "boundary-001",
        fixture_id="canonical-boundary-001",
        title="Boundary report",
    )
    outside = tmp_path / "outside-report.md"
    outside.write_text("# Boundary report\n\nExternal bytes.\n", encoding="utf-8")
    data = yaml.safe_load((fixture_dir / "manifest.yaml").read_text(encoding="utf-8"))
    if mode == "symlink":
        link = fixture_dir / "outside-link.md"
        link.symlink_to(outside)
        report_path = "canonical/boundary-001/outside-link.md"
    else:
        report_path = _escape_path(mode, root=corpus, outside=outside, link_name="unused")
    data["report"]["path"] = report_path
    (fixture_dir / "manifest.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )

    with pytest.raises(FixtureError, match="report\\.path.*(relative|allowed root)") as caught:
        load_canonical_fixture(fixture_dir, corpus)
    assert str(outside) not in caught.value.args[0] or "allowed root" in str(caught.value)


def _write_outside_derived(case_dir: Path, report_path: str) -> None:
    case_dir.mkdir(parents=True)
    (case_dir / "report.md").write_text("# Derived boundary case\n\nExternal.\n", encoding="utf-8")
    manifest = {
        "id": "mut-boundary-001",
        "parent_id": "canonical-parent-001",
        "operator": "impact_inflation",
        "category": "impact",
        "parameters": {},
        "seed": 1,
        "variant_index": 0,
        "base_seed": 1,
        "expected_decision": "accept",
        "expected_dimensions": {},
        "generator_version": "test",
        "report": {"path": report_path},
    }
    (case_dir / "mutation-manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )


@pytest.mark.parametrize("mode", ["absolute", "parent", "symlink"])
def test_suite_manifest_path_cannot_escape_materialized_root(tmp_path: Path, mode: str) -> None:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus, "parent-001", fixture_id="canonical-parent-001", title="Parent report"
    )
    materialized = tmp_path / "materialized"
    materialized.mkdir()
    outside_case = tmp_path / "outside-case"
    if mode == "absolute":
        report_path = str((outside_case / "report.md").resolve())
        manifest_path = str((outside_case / "mutation-manifest.yaml").resolve())
    elif mode == "parent":
        report_path = "../outside-case/report.md"
        manifest_path = "../outside-case/mutation-manifest.yaml"
    else:
        report_path = "outside-link/report.md"
        manifest_path = "outside-link/mutation-manifest.yaml"
    _write_outside_derived(outside_case, report_path)
    if mode == "symlink":
        (materialized / "outside-link").symlink_to(outside_case, target_is_directory=True)
    index = materialized / "suite-index.jsonl"
    index.write_text(
        json.dumps({"record_type": "suite_header"})
        + "\n"
        + json.dumps(
            {
                "record_type": "suite_case",
                "kind": "mutated",
                "case_id": "mut-boundary-001",
                "manifest_path": manifest_path,
                "report_class": "valid",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(FixtureError, match="suite manifest_path.*(relative|allowed root)"):
        build_cases(index, corpus, materialized)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("binding", ["records", "outcomes"])
@pytest.mark.parametrize("mode", ["absolute", "parent", "symlink"])
def test_analysis_bound_path_cannot_escape_bundle(tmp_path: Path, binding: str, mode: str) -> None:
    out_dir = _published_run(tmp_path, f"path-{binding}-{mode}")
    marker = out_dir / analysis_filename()
    document = json.loads(marker.read_text(encoding="utf-8"))

    if binding == "records":
        source = out_dir / "records.jsonl"
        outside = tmp_path / f"outside-records-{mode}.jsonl"
        outside.write_bytes(source.read_bytes())
    else:
        outside = tmp_path / f"outside-outcomes-{mode}.jsonl"
        outside.write_text("", encoding="utf-8")

    if mode == "absolute":
        injected = str(outside.resolve())
    elif mode == "parent":
        injected = f"../{outside.name}"
    else:
        link = out_dir / f"escape-{binding}.jsonl"
        link.symlink_to(outside)
        injected = link.name

    if binding == "records":
        document["records_path"] = injected
        document["records_sha256"] = _sha256(outside)
        document["records_count"] = len(
            [line for line in outside.read_text(encoding="utf-8").splitlines() if line.strip()]
        )
    else:
        document["outcomes"] = {
            "present": True,
            "path": injected,
            "sha256": _sha256(outside),
            "lines": 0,
        }

    marker.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    write_completion(out_dir, kind="study")

    with pytest.raises(AnalysisError, match="analysis .*path.*(relative|allowed root)"):
        read_versioned_analysis(marker)


def test_valid_in_root_paths_still_work(tmp_path: Path) -> None:
    out_dir = _published_run(tmp_path, "path-valid")
    document = read_versioned_analysis(out_dir / analysis_filename())
    assert document["records_path"] == "records.jsonl"
