"""Cleanup faults must not lie about whether a canonical fixture was committed."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, cast

import pytest
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.corpus import add_report as core
from sloplab.corpus.atomic import publish_directory
from sloplab.corpus.loader import CanonicalFixture, DerivedFixture, discover_fixtures
from sloplab.corpus.validation import ValidationResult, validate_corpus
from tests._add_report_helpers import answers, make_corpus, make_manifest, make_source, snapshot


def _inject_cleanup_failure(
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    error_type: type[BaseException],
    *,
    remove_first: bool = False,
) -> list[Path]:
    """Fault only the lock/stage cleanup syscall, never publication or rollback.

    Patching rmtree below TemporaryDirectory.cleanup exercises real finalizer
    detachment and leaves real scratch data when deletion fails before removal.
    """
    paths: list[Path] = []
    original_rmdir = Path.rmdir
    original_rmtree = cast(Any, tempfile.TemporaryDirectory)._rmtree

    def rmdir(path: Path) -> None:
        if target in ("lock", "both") and path.name.endswith(".sloplab-add-report.lock"):
            paths.append(path)
            if remove_first:
                original_rmdir(path)
            raise error_type("injected lock cleanup")
        original_rmdir(path)

    def rmtree(
        cls: type[tempfile.TemporaryDirectory[str]], path: str, *args: Any, **kwargs: Any
    ) -> None:
        if target in ("stage", "both") and Path(path).name.startswith(".sloplab-stage-"):
            paths.append(Path(path))
            if remove_first:
                original_rmtree(path, *args, **kwargs)
            raise error_type("injected stage cleanup")
        original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(Path, "rmdir", rmdir)
    monkeypatch.setattr(tempfile.TemporaryDirectory, "_rmtree", classmethod(rmtree))
    return paths


def _assert_committed(
    root: Path, before: dict[str, bytes | None], result: core.AddReportResult
) -> None:
    assert result.committed is True
    assert result.destination == root / "canonical/new-001"
    after = snapshot(root)
    added = {"canonical/new-001", "canonical/new-001/report.md", "canonical/new-001/manifest.yaml"}
    assert {key: value for key, value in after.items() if key not in added} == before
    assert set(after) - set(before) == added
    canonical, derived = discover_fixtures(root)
    assert validate_corpus(canonical, derived, root).ok
    assert result.validation.ok
    assert result.validation.checked_canonical == result.before_count + 1


@pytest.mark.parametrize("error_type", [OSError, KeyboardInterrupt])
@pytest.mark.parametrize("remove_first", [False, True])
def test_lock_cleanup_failure_preserves_verified_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[BaseException],
    remove_first: bool,
) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)
    paths = _inject_cleanup_failure(monkeypatch, "lock", error_type, remove_first=remove_first)
    with core.prepare_add_report(source, make_manifest(source), root) as prepared:
        result = core.commit_add_report(prepared, confirmed=True)
        assert prepared.commit_result is result
    _assert_committed(root, before, result)
    assert source.path.read_bytes() == source.content == result.report_path.read_bytes()
    assert paths == [tmp_path / ".corpus.sloplab-add-report.lock"]
    assert paths[0].exists() is not remove_first
    assert len(result.cleanup_warnings) == 1
    assert "lock cleanup incomplete" in result.cleanup_warnings[0]
    assert error_type.__name__ in result.cleanup_warnings[0]
    assert str(paths[0]) in result.cleanup_warnings[0]
    assert not list(tmp_path.glob(".sloplab-stage-*"))


@pytest.mark.parametrize("error_type", [OSError, KeyboardInterrupt])
@pytest.mark.parametrize("remove_first", [False, True])
def test_stage_cleanup_failure_preserves_verified_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[BaseException],
    remove_first: bool,
) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)
    paths = _inject_cleanup_failure(monkeypatch, "stage", error_type, remove_first=remove_first)
    with core.prepare_add_report(source, make_manifest(source), root) as prepared:
        result = core.commit_add_report(prepared, confirmed=True)
        # Stage cleanup happens AFTER commit returns; the same result must survive.
        assert result.cleanup_warnings == []
    assert prepared.commit_result is result
    _assert_committed(root, before, result)
    assert source.path.read_bytes() == source.content == result.report_path.read_bytes()
    assert paths == [prepared.staged_directory.parents[1]]
    assert paths[0].exists() is not remove_first
    assert len(result.cleanup_warnings) == 1
    assert "stage cleanup incomplete" in result.cleanup_warnings[0]
    assert error_type.__name__ in result.cleanup_warnings[0]
    assert str(paths[0]) in result.cleanup_warnings[0]
    assert not (tmp_path / ".corpus.sloplab-add-report.lock").exists()


@pytest.mark.parametrize("target", ["lock", "stage", "both"])
@pytest.mark.parametrize("error_type", [OSError, KeyboardInterrupt])
def test_cli_cleanup_failure_reports_committed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str, error_type: type[BaseException]
) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)
    paths = _inject_cleanup_failure(monkeypatch, target, error_type)
    result = CliRunner().invoke(
        cli, ["add-report", str(source.path), "--corpus", str(root)], input=answers()
    )
    assert result.exit_code == 0, result.output
    assert "Fixture added: canonical-new-001" in result.output
    assert "Fixture committed; cleanup incomplete" in result.output
    assert "Do not retry add-report" in result.output
    assert "cannot prepare fixture" not in result.output
    assert "cannot commit fixture" not in result.output
    assert "Aborted" not in result.output
    assert len(paths) == (2 if target == "both" else 1)
    for path in paths:
        assert str(path) in result.output
    after = snapshot(root)
    assert all(after[key] == value for key, value in before.items())
    assert source.path.read_bytes() == source.content
    assert (root / "canonical/new-001/report.md").read_bytes() == source.content


@pytest.mark.parametrize("target", ["lock", "stage", "both"])
@pytest.mark.parametrize("cleanup_error", [OSError, KeyboardInterrupt])
@pytest.mark.parametrize("primary_error", [core.AddReportError, KeyboardInterrupt])
def test_cleanup_failure_preserves_primary_error_and_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    cleanup_error: type[BaseException],
    primary_error: type[BaseException],
) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)
    paths = _inject_cleanup_failure(monkeypatch, target, cleanup_error)
    original = primary_error("injected immediately after publication")

    def fail_after_publish(pending: Path, destination: Path) -> None:
        publish_directory(pending, destination)
        raise original

    monkeypatch.setattr(core, "publish_directory", fail_after_publish)
    with (
        pytest.raises(primary_error) as caught,
        core.prepare_add_report(source, make_manifest(source), root) as prepared,
    ):
        core.commit_add_report(prepared, confirmed=True)
    assert caught.value is original
    assert prepared.commit_result is None
    assert snapshot(root) == before
    assert source.path.read_bytes() == source.content
    notes = "\n".join(original.__notes__)
    assert len(paths) == (2 if target == "both" else 1)
    assert all(str(path) in notes for path in paths)


@pytest.mark.parametrize("cleanup_error", [OSError, KeyboardInterrupt])
@pytest.mark.parametrize("caller_error", [OSError, KeyboardInterrupt])
def test_stage_cleanup_does_not_swallow_caller_error_after_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_error: type[BaseException],
    caller_error: type[BaseException],
) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)
    paths = _inject_cleanup_failure(monkeypatch, "stage", cleanup_error)
    original = caller_error("unrelated caller error after commit")
    with (
        pytest.raises(caller_error) as caught,
        core.prepare_add_report(source, make_manifest(source), root) as prepared,
    ):
        result = core.commit_add_report(prepared, confirmed=True)
        raise original
    assert caught.value is original
    assert prepared.commit_result is result
    _assert_committed(root, before, result)
    assert len(result.cleanup_warnings) == 1
    assert str(paths[0]) in result.cleanup_warnings[0]
    assert "Fixture committed" in "\n".join(original.__notes__)


@pytest.mark.parametrize("error_type", [OSError, KeyboardInterrupt])
def test_stage_cleanup_without_commit_is_not_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: type[BaseException]
) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)
    _inject_cleanup_failure(monkeypatch, "stage", error_type)
    expected = core.AddReportError if error_type is OSError else KeyboardInterrupt
    with (
        pytest.raises(expected),
        core.prepare_add_report(source, make_manifest(source), root) as prepared,
    ):
        pass  # Cancel, not a successful commit: cleanup failure must not imply success.
    assert prepared.commit_result is None
    assert snapshot(root) == before
    assert source.path.read_bytes() == source.content


@pytest.mark.parametrize("error_type", [OSError, KeyboardInterrupt])
def test_postwrite_validation_failure_with_cleanup_faults_remains_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: type[BaseException]
) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)
    paths = _inject_cleanup_failure(monkeypatch, "both", error_type)

    def fail_postwrite(
        canonical: list[CanonicalFixture],
        derived: list[DerivedFixture],
        corpus_root: Path | None = None,
    ) -> ValidationResult:
        validation = validate_corpus(canonical, derived, corpus_root)
        if (root / "canonical/new-001").exists():
            validation.error("injected", "invalid after publication")
        return validation

    monkeypatch.setattr(core, "validate_corpus", fail_postwrite)
    with (
        pytest.raises(core.AddReportError, match="post-write full corpus validation") as caught,
        core.prepare_add_report(source, make_manifest(source), root) as prepared,
    ):
        core.commit_add_report(prepared, confirmed=True)
    assert prepared.commit_result is None
    assert caught.value.validation is not None and not caught.value.validation.ok
    assert snapshot(root) == before
    assert source.path.read_bytes() == source.content
    assert len(paths) == 2
    assert all(str(path) in "\n".join(caught.value.__notes__) for path in paths)


@pytest.mark.parametrize("error_type", [OSError, KeyboardInterrupt])
def test_incomplete_rollback_is_not_hidden_by_cleanup_faults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: type[BaseException]
) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)
    paths = _inject_cleanup_failure(monkeypatch, "both", error_type)

    def fail_after_publish(pending: Path, destination: Path) -> None:
        publish_directory(pending, destination)
        raise core.AddReportError("injected before final validation")

    def fail_rollback(destination: Path, identity: tuple[int, int] | None) -> None:
        raise OSError(f"cannot remove {destination}")

    monkeypatch.setattr(core, "publish_directory", fail_after_publish)
    monkeypatch.setattr(core, "_rollback", fail_rollback)
    with (
        pytest.raises(core.AddReportError, match="rollback incomplete") as caught,
        core.prepare_add_report(source, make_manifest(source), root) as prepared,
    ):
        core.commit_add_report(prepared, confirmed=True)
    assert prepared.commit_result is None  # Published is NOT equivalent to verified commit.
    assert prepared.destination.is_dir()
    assert str(prepared.destination) in str(caught.value)
    assert all(snapshot(root)[key] == value for key, value in before.items())
    assert source.path.read_bytes() == source.content
    assert len(paths) == 2
    assert all(str(path) in "\n".join(caught.value.__notes__) for path in paths)


def test_committed_plan_cannot_be_retried_or_lose_its_result(tmp_path: Path) -> None:
    root = make_corpus(tmp_path)
    source = make_source(tmp_path)
    with core.prepare_add_report(source, make_manifest(source), root) as prepared:
        result = core.commit_add_report(prepared, confirmed=True)
        committed_tree = snapshot(root)
        with pytest.raises(core.AddReportError, match="already committed"):
            core.commit_add_report(prepared, confirmed=True)
        assert prepared.commit_result is result
        assert snapshot(root) == committed_tree
    assert result.cleanup_warnings == []


@pytest.mark.parametrize("error_type", [OSError, KeyboardInterrupt])
def test_cli_primary_io_failure_keeps_cleanup_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: type[BaseException]
) -> None:
    root = make_corpus(tmp_path)
    before = snapshot(root)
    source = make_source(tmp_path)
    paths = _inject_cleanup_failure(monkeypatch, "both", error_type)

    def fail(pending: Path, destination: Path) -> None:
        raise OSError("injected publication failure")

    monkeypatch.setattr(core, "publish_directory", fail)
    result = CliRunner().invoke(
        cli, ["add-report", str(source.path), "--corpus", str(root)], input=answers()
    )
    assert result.exit_code != 0
    assert "injected publication failure" in result.output
    assert "Fixture added" not in result.output
    assert len(paths) == 2
    assert all(str(path) in result.output for path in paths)
    assert snapshot(root) == before
