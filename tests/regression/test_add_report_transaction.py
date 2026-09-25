"""Transaction fault injection: failures never overwrite or retain a partial fixture."""

from __future__ import annotations

import errno
from dataclasses import replace
from pathlib import Path

import pytest
from click.testing import CliRunner

import sloplab.corpus.add_report as core
from sloplab.cli.main import cli
from sloplab.corpus.atomic import publish_directory
from sloplab.corpus.loader import CanonicalFixture, DerivedFixture, discover_fixtures
from sloplab.corpus.validation import ValidationResult, validate_corpus
from tests._add_report_helpers import (
    REPORT,
    answers,
    make_corpus,
    make_manifest,
    make_source,
    snapshot,
)
from tests._helpers import write_canonical_fixture


@pytest.mark.parametrize("line_endings", ["lf", "crlf"])
def test_happy_path_preserves_source_and_all_existing_bytes(
    tmp_path: Path, line_endings: str
) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    body = REPORT if line_endings == "lf" else REPORT.replace("\n", "\r\n")
    source = make_source(tmp_path, body.encode())
    with core.prepare_add_report(source, make_manifest(source), root) as prepared:
        assert not prepared.destination.exists()
        result = core.commit_add_report(prepared, confirmed=True)
        assert result.validation.ok
        assert result.before_count == 1 and result.validation.checked_canonical == 2
        assert result.report_path.read_bytes() == source.content
    assert source.path.read_bytes() == source.content
    after = snapshot(root)
    assert all(after[k] == v for k, v in before.items())
    canonical, derived = discover_fixtures(root)
    assert validate_corpus(canonical, derived, root).ok
    assert not list(tmp_path.glob(".sloplab-stage-*"))
    assert not list(root.rglob(".sloplab-commit-*"))
    assert not (tmp_path / ".corpus.sloplab-add-report.lock").exists()


def test_explicit_confirmation_required(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)
    with (
        core.prepare_add_report(source, make_manifest(source), root) as prepared,
        pytest.raises(core.AddReportError, match="confirmation"),
    ):
        core.commit_add_report(prepared)
    assert snapshot(root) == before


@pytest.mark.parametrize("kind", ["fixture", "empty-directory", "file", "alternate-id-directory"])
def test_collisions_never_overwrite(tmp_path: Path, kind: str) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    dest = root / "canonical/new-001"
    if kind in {"fixture", "alternate-id-directory"}:
        name = "new-001" if kind == "fixture" else "canonical-new-001"
        write_canonical_fixture(
            root, name, fixture_id="canonical-new-001", title="Existing collision"
        )
    elif kind == "empty-directory":
        dest.mkdir()
    else:
        dest.write_bytes(b"do not overwrite")
    before = snapshot(root)
    with (
        pytest.raises(core.AddReportError, match="exists|duplicate"),
        core.prepare_add_report(source, make_manifest(source), root),
    ):
        pytest.fail("collision was accepted")
    assert snapshot(root) == before
    assert source.path.read_bytes() == source.content


@pytest.mark.parametrize(
    "failure", ["safety", "evidence", "unknown-evidence", "schema", "h1-mismatch", "path", "pair"]
)
def test_invalid_fixture_never_changes_corpus(tmp_path: Path, failure: str) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    content = REPORT + ("\nhttps://real-target.invalid\n" if failure == "safety" else "")
    source = make_source(tmp_path, content.encode())
    manifest = make_manifest(source)
    if failure == "evidence":
        manifest.ground_truth.required_evidence = ["affected_versions"]
    elif failure == "unknown-evidence":
        manifest.ground_truth.required_evidence = ["made_up"]
    elif failure == "schema":
        manifest.ground_truth.expected_dimensions["reproducibility"] = 1.2
    elif failure == "h1-mismatch":
        manifest.title = "A different title"
    elif failure == "path":
        manifest.report.path = "../escape/report.md"
    elif failure == "pair":
        manifest = manifest.model_copy(update={"pair_id": "pair-x", "pair_role": "plain"})
    with pytest.raises(core.AddReportError), core.prepare_add_report(source, manifest, root):
        pytest.fail("invalid fixture was accepted")
    assert snapshot(root) == before
    assert not list(tmp_path.glob(".sloplab-stage-*"))


def test_real_corpus_invariant_failure_blocks_preflight(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    write_canonical_fixture(
        root, "lonely", fixture_id="canonical-lonely", title="Broken pair", pair_id="pair-lonely"
    )
    before = snapshot(root)
    source = make_source(tmp_path)
    with (
        pytest.raises(core.AddReportError, match="full corpus preflight"),
        core.prepare_add_report(source, make_manifest(source), root),
    ):
        pytest.fail("invalid existing corpus was accepted")
    assert snapshot(root) == before


@pytest.mark.parametrize("phase", ["commit-preflight", "post-write"])
def test_validation_faults_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)
    destination = root / "canonical/new-001"

    def fail(
        canonical: list[CanonicalFixture],
        derived: list[DerivedFixture],
        corpus_root: Path | None = None,
    ) -> ValidationResult:
        result = validate_corpus(canonical, derived, corpus_root)
        if phase == "commit-preflight" or destination.exists():
            result.error("injected", phase)
        return result

    with core.prepare_add_report(source, make_manifest(source), root) as prepared:
        monkeypatch.setattr(core, "validate_corpus", fail)
        with pytest.raises(core.AddReportError, match="failed"):
            core.commit_add_report(prepared, confirmed=True)
    assert snapshot(root) == before
    assert source.path.read_bytes() == source.content
    assert not (tmp_path / ".corpus.sloplab-add-report.lock").exists()


@pytest.mark.parametrize("failure", ["io", "interrupt-before", "interrupt-after"])
def test_rename_faults_and_interruptions_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)

    def fail(pending: Path, destination: Path) -> None:
        if failure == "io":
            raise OSError(errno.ENOSPC, "injected disk error")
        if failure == "interrupt-after":
            publish_directory(pending, destination)
        raise KeyboardInterrupt

    with core.prepare_add_report(source, make_manifest(source), root) as prepared:
        monkeypatch.setattr(core, "publish_directory", fail)
        with pytest.raises(core.AddReportError if failure == "io" else KeyboardInterrupt):
            core.commit_add_report(prepared, confirmed=True)
    assert snapshot(root) == before
    assert not list(tmp_path.glob(".sloplab-stage-*"))
    assert not (tmp_path / ".corpus.sloplab-add-report.lock").exists()


def test_new_empty_corpus_creation_and_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    source = make_source(tmp_path)

    def fail(pending: Path, destination: Path) -> None:
        raise OSError(errno.ENOSPC, "disk full")

    with core.prepare_add_report(source, make_manifest(source), root) as prepared:
        assert not (root / "canonical").exists()
        with monkeypatch.context() as patch:
            patch.setattr(core, "publish_directory", fail)
            with pytest.raises(core.AddReportError):
                core.commit_add_report(prepared, confirmed=True)
        assert snapshot(root) == {}
        result = core.commit_add_report(prepared, confirmed=True)
        assert result.before_count == 0 and result.validation.checked_canonical == 1


@pytest.mark.parametrize("changed", ["source", "stage", "corpus", "destination"])
def test_stale_preview_refused(tmp_path: Path, changed: str) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    with core.prepare_add_report(source, make_manifest(source), root) as prepared:
        if changed == "source":
            source.path.write_bytes(source.content + b"\nExternal edit\n")
        elif changed == "stage":
            (prepared.staged_directory / "report.md").write_text(REPORT + "tampered")
        elif changed == "corpus":
            (root / "external-file").write_bytes(b"external edit")
        else:
            prepared.destination.mkdir()
        externally_changed = snapshot(root)
        with pytest.raises(core.AddReportError, match="changed"):
            core.commit_add_report(prepared, confirmed=True)
        assert snapshot(root) == externally_changed


def test_expired_stage_cannot_be_committed(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    before = snapshot(root)
    with core.prepare_add_report(source, make_manifest(source), root) as prepared:
        pass
    with pytest.raises(core.AddReportError):
        core.commit_add_report(prepared, confirmed=True)
    assert snapshot(root) == before


def test_no_replace_even_when_empty_destination_appears_at_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    before = snapshot(root)

    def race(pending: Path, destination: Path) -> None:
        destination.mkdir()  # created AFTER the last existence check
        publish_directory(pending, destination)

    with core.prepare_add_report(source, make_manifest(source), root) as prepared:
        monkeypatch.setattr(core, "publish_directory", race)
        with pytest.raises(core.AddReportError):
            core.commit_add_report(prepared, confirmed=True)
        assert prepared.destination.is_dir()
        assert list(prepared.destination.iterdir()) == []
    after = snapshot(root)
    del after["canonical/new-001"]  # external writer's directory is preserved
    assert after == before


def test_destination_symlink_and_canonical_symlink_refused(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "canonical/new-001").symlink_to(outside, target_is_directory=True)
    with (
        pytest.raises(core.AddReportError, match="symlinks"),
        core.prepare_add_report(source, make_manifest(source), root),
    ):
        pytest.fail("symlink was accepted")
    assert list(outside.iterdir()) == []


def test_stale_or_active_lock_is_not_stolen(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    before = snapshot(root)
    with core.prepare_add_report(source, make_manifest(source), root) as prepared:
        lock = tmp_path / ".corpus.sloplab-add-report.lock"
        lock.mkdir()
        with pytest.raises(core.AddReportError, match="lock"):
            core.commit_add_report(prepared, confirmed=True)
        assert lock.is_dir()
    assert snapshot(root) == before


def test_modified_destination_in_plan_is_rejected(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    before = snapshot(root)
    with (
        core.prepare_add_report(source, make_manifest(source), root) as prepared,
        pytest.raises(core.AddReportError, match="destination"),
    ):
        core.commit_add_report(replace(prepared, destination=tmp_path / "escape"), confirmed=True)
    assert snapshot(root) == before
    assert not (tmp_path / "escape").exists()


def test_cli_postwrite_failure_never_prints_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)

    def fail(
        canonical: list[CanonicalFixture],
        derived: list[DerivedFixture],
        corpus_root: Path | None = None,
    ) -> ValidationResult:
        result = validate_corpus(canonical, derived, corpus_root)
        if (root / "canonical/new-001").exists():
            result.error("injected", "post-write")
        return result

    monkeypatch.setattr(core, "validate_corpus", fail)
    result = CliRunner().invoke(
        cli, ["add-report", str(source.path), "--corpus", str(root)], input=answers()
    )
    assert result.exit_code != 0
    assert "post-write" in result.output
    assert "Fixture added" not in result.output
    assert snapshot(root) == before


def test_missing_corpus_is_not_silently_created(tmp_path: Path) -> None:
    root = tmp_path / "missing"
    source = make_source(tmp_path)
    with (
        pytest.raises(core.AddReportError),
        core.prepare_add_report(source, make_manifest(source), root),
    ):
        pytest.fail("missing corpus accepted")
    assert not root.exists()


def test_existing_external_report_reference_refused(tmp_path: Path) -> None:
    import yaml

    root = make_corpus(tmp_path)
    path = root / "canonical/existing/manifest.yaml"
    data = yaml.safe_load(path.read_text())
    outside = tmp_path / "outside.md"
    outside.write_bytes((root / "canonical/existing/report.md").read_bytes())
    data["report"]["path"] = str(outside)
    path.write_text(yaml.safe_dump(data))
    before = snapshot(root)
    source = make_source(tmp_path)
    with (
        pytest.raises(core.AddReportError, match="escapes corpus"),
        core.prepare_add_report(source, make_manifest(source), root),
    ):
        pytest.fail("external reference accepted")
    assert snapshot(root) == before


def test_changed_commit_bytes_are_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    before = snapshot(root)

    def corrupt(pending: Path, destination: Path) -> None:
        # Still a valid report: must fail byte identity, not just schema/safety.
        with (pending / "report.md").open("ab") as handle:
            handle.write(b"\nUnexpected change\n")
        publish_directory(pending, destination)

    with core.prepare_add_report(source, make_manifest(source), root) as prepared:
        monkeypatch.setattr(core, "publish_directory", corrupt)
        with pytest.raises(core.AddReportError, match="bytes differ"):
            core.commit_add_report(prepared, confirmed=True)
    assert snapshot(root) == before


def test_rollback_failure_is_reported_not_hidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)

    def fail_validation(
        canonical: list[CanonicalFixture],
        derived: list[DerivedFixture],
        corpus_root: Path | None = None,
    ) -> ValidationResult:
        result = validate_corpus(canonical, derived, corpus_root)
        if (root / "canonical/new-001").exists():
            result.error("injected", "post-write")
        return result

    def fail_rollback(destination: Path, identity: tuple[int, int] | None) -> None:
        raise OSError(errno.EACCES, "injected permission failure", str(destination))

    with core.prepare_add_report(source, make_manifest(source), root) as prepared:
        monkeypatch.setattr(core, "validate_corpus", fail_validation)
        monkeypatch.setattr(core, "_rollback", fail_rollback)
        with pytest.raises(core.AddReportError, match="rollback incomplete"):
            core.commit_add_report(prepared, confirmed=True)
        assert prepared.destination.is_dir()  # explicitly reported, never hidden
    assert (root / "canonical/existing/report.md").is_file()


def test_atomic_publish_fails_closed_on_unsupported_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    import sys

    import sloplab.corpus.atomic as atomic

    pending, destination = tmp_path / "pending", tmp_path / "destination"
    pending.mkdir()
    monkeypatch.setattr(sys, "platform", "unsupported")
    if os.name == "nt":
        pytest.skip("Windows uses its own no-replace rename")
    with pytest.raises(OSError, match="unavailable"):
        atomic.publish_directory(pending, destination)
    assert pending.is_dir() and not destination.exists()
