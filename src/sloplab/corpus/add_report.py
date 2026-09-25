"""UI-independent, staged canonical-fixture creation.

Public flow: read_report -> build_manifest -> prepare_add_report (context manager)
-> show preview / obtain approval -> commit_add_report(confirmed=True).
No Click, subprocesses, network access, parallel schemas or evaluator calls.
See docs/add-report.md for lifecycle, concurrency and crash-recovery boundaries.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from sloplab.corpus.atomic import publish_directory
from sloplab.corpus.conventions import EVIDENCE_SECTION_PATTERNS
from sloplab.corpus.loader import (
    SUITE_INDEX_NAME,
    CanonicalFixture,
    DerivedFixture,
    FixtureError,
    discover_fixtures,
    format_validation_error,
    load_canonical_fixture,
)
from sloplab.corpus.parser import parse_report
from sloplab.corpus.validation import ValidationResult, validate_canonical_fixture, validate_corpus
from sloplab.models.enums import ReportClass
from sloplab.models.manifest import CanonicalManifest, GroundTruth, ReportRef


class AddReportError(ValueError):
    """Actionable creation failure, optionally carrying existing validator output."""

    def __init__(self, message: str, validation: ValidationResult | None = None) -> None:
        self.validation = validation
        super().__init__(message if validation is None else f"{message}\n{validation.render()}")


@dataclass(frozen=True)
class ReportSource:
    path: Path
    content: bytes
    title: str
    evidence_keys: tuple[str, ...]


def read_report(path: Path) -> ReportSource:
    """Snapshot UTF-8 bytes and detect H1/evidence with the existing parser."""
    try:
        path = path.resolve(strict=True)
        if not path.is_file():
            raise AddReportError(f"source is not a regular file: {path}")
        content = path.read_bytes()
        document = parse_report(content.decode("utf-8"), fixture_id="source", path=str(path))
    except (OSError, UnicodeError) as exc:
        raise AddReportError(f"cannot read UTF-8 report '{path}': {exc}") from exc
    h1 = next((s.heading for s in document.sections if s.level == 1 and s.heading), None)
    if h1 is None:
        raise AddReportError("report has no H1 heading; add '# Report title' outside code fences")
    evidence = tuple(
        k for k, pattern in EVIDENCE_SECTION_PATTERNS.items() if document.find_sections(pattern)
    )
    return ReportSource(path, content, h1, evidence)


def build_manifest(
    source: ReportSource,
    *,
    slug: str,
    report_class: ReportClass,
    ground_truth: GroundTruth,
    sanitization_note: str = "",
) -> CanonicalManifest:
    """Use the canonical models for ID, enum and dimension validation."""
    try:
        manifest = CanonicalManifest(
            id=f"canonical-{slug}",
            title=source.title,
            report_class=report_class,
            ground_truth=ground_truth,
            report=ReportRef(path=f"canonical/{slug}/report.md"),
            sanitization_note=sanitization_note,
        )
        # Revalidate nested data too: callers can mutate a Pydantic dict in place.
        return CanonicalManifest.model_validate(manifest.model_dump(mode="json"))
    except ValidationError as exc:
        raise AddReportError(f"invalid manifest:\n{format_validation_error(exc)}") from exc


def manifest_yaml(manifest: CanonicalManifest) -> str:
    """Stable YAML of an existing schema, not a separate serializer schema."""
    return yaml.safe_dump(
        manifest.model_dump(mode="json", exclude_none=True), sort_keys=False, allow_unicode=True
    )


@dataclass
class _CommitState:
    # Shared with the preparation context so stage cleanup can amend the SAME
    # result after commit_add_report returns. Never set merely on publication.
    result: AddReportResult | None = None


@dataclass(frozen=True)
class PreparedReport:
    """Review snapshot. Valid only inside prepare_add_report's context lifetime.

    manifest returns a fresh model; modifying a preview cannot change the commit.
    preflight exposes real errors/warnings, never synthetic UI status indicators.
    """

    source: ReportSource
    corpus_root: Path
    destination: Path
    staged_directory: Path
    manifest_text: str
    fixture_validation: ValidationResult
    preflight: ValidationResult
    _corpus_digest: str
    _root_identity: tuple[int, int]
    _stage_digest: str
    _state: _CommitState = field(default_factory=_CommitState, repr=False, compare=False)

    @property
    def commit_result(self) -> AddReportResult | None:
        """Verified commit outcome, also available after the preparation context exits."""
        return self._state.result

    @property
    def manifest(self) -> CanonicalManifest:
        return CanonicalManifest.model_validate(yaml.safe_load(self.manifest_text))


@dataclass(frozen=True)
class AddReportResult:
    fixture_id: str
    destination: Path
    report_path: Path
    manifest_path: Path
    before_count: int
    validation: ValidationResult
    # Lock cleanup is known on return; stage cleanup appends on context exit.
    # Consumers must read this after closing prepare_add_report / ExitStack.
    cleanup_warnings: list[str] = field(default_factory=list, compare=False)

    @property
    def committed(self) -> bool:
        """A result exists only after publication AND all final checks succeeded."""
        return True


def _cleanup_failed(
    kind: str,
    path: Path,
    cleanup: BaseException,
    state: _CommitState,
    active_error: BaseException | None,
) -> None:
    """Keep resource cleanup separate from the verified transaction outcome.

    Called only for an exception from a cleanup operation, never around yield or
    a caller's code. An earlier failure/interrupt must remain the primary error.
    """
    warning = f"{kind} cleanup incomplete at '{path}': {type(cleanup).__name__}: {cleanup}"
    if state.result is not None:
        state.result.cleanup_warnings.append(warning)
        if active_error is not None:
            active_error.add_note(f"Fixture committed at {state.result.destination}; {warning}")
    elif active_error is not None:
        active_error.add_note(warning)
    elif isinstance(cleanup, KeyboardInterrupt):
        cleanup.add_note(f"Fixture was not committed; {warning}")
        raise cleanup
    else:
        raise AddReportError(f"fixture was not committed; {warning}") from cleanup


def _identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise AddReportError(f"expected a real directory, not a symlink: {path}")
    return info.st_dev, info.st_ino


def _walk_error(error: OSError) -> None:
    raise error


def _tree_digest(
    root: Path, *, exclude: Path | None = None, omit_directory: Path | None = None
) -> str:
    """Snapshot names/types/bytes, rejecting links and special files, not following them."""
    _identity(root)
    digest = hashlib.sha256()
    for directory, names, files in os.walk(root, followlinks=False, onerror=_walk_error):
        names.sort()
        files.sort()
        parent = Path(directory)
        if exclude is not None and exclude.parent == parent:
            names[:] = [name for name in names if parent / name != exclude]
            files = [name for name in files if parent / name != exclude]
        for name in sorted([*names, *files]):
            path = parent / name
            info = path.lstat()
            relative = path.relative_to(root).as_posix()
            if stat.S_ISDIR(info.st_mode):
                if path != omit_directory:
                    digest.update(f"D:{relative}\0".encode())
            elif stat.S_ISREG(info.st_mode):
                digest.update(f"F:{relative}\0".encode())
                with path.open("rb") as handle:
                    digest.update(hashlib.file_digest(handle, "sha256").digest())
            else:
                raise AddReportError(
                    f"symlinks and special files are not supported in this write workflow: {path}"
                )
    return digest.hexdigest()


def _source_unchanged(source: ReportSource) -> None:
    if source.path.read_bytes() != source.content:
        raise AddReportError("source changed since preview; prepare and review it again")


def _require_ok(result: ValidationResult, phase: str) -> None:
    if not result.ok:
        raise AddReportError(f"{phase} failed; fixture was not accepted", result)


def _preflight(root: Path, staged: CanonicalFixture, destination: Path) -> ValidationResult:
    # lexists also rejects a dangling destination symlink.
    if os.path.lexists(destination):
        raise AddReportError(f"destination already exists; never overwritten: {destination}")
    canonical, derived = discover_fixtures(root)
    ids = [fixture.fixture_id for fixture in canonical]
    if staged.fixture_id in ids or len(ids) != len(set(ids)):
        raise AddReportError(
            "duplicate canonical ID; choose a new slug or repair the existing corpus"
        )
    fixtures: list[CanonicalFixture | DerivedFixture] = [*canonical, *derived]
    for fixture in fixtures:
        if not (root / fixture.manifest.report.path).resolve().is_relative_to(root):
            raise AddReportError(
                f"existing report.path escapes corpus: {fixture.manifest.report.path}"
            )
    result = validate_corpus([*canonical, staged], derived, corpus_root=root)
    _require_ok(result, "full corpus preflight")
    return result


@contextmanager
def prepare_add_report(
    source: ReportSource, manifest: CanonicalManifest, corpus_root: Path
) -> Iterator[PreparedReport]:
    """Stage outside the corpus, validate and yield a read-only review snapshot.

    Exiting attempts stage cleanup. After a verified commit, cleanup-only failures
    are appended to its result.cleanup_warnings rather than losing commit success.
    Exceptions from the caller's with-body propagate unchanged. The corpus
    root must exist; a missing canonical/ is created only after explicit approval.
    Pair creation/editing and report paths outside canonical/<slug>/ are excluded.
    """
    state = _CommitState()
    temporary: tempfile.TemporaryDirectory[str] | None = None
    active_error: BaseException | None = None
    try:
        try:
            root = corpus_root.resolve(strict=True)
            if root == root.parent:
                raise AddReportError("a filesystem root cannot be used as a corpus")
            root_identity = _identity(root)
            before = _tree_digest(root)
            manifest = CanonicalManifest.model_validate(manifest.model_dump(mode="json"))
            slug = manifest.id.removeprefix("canonical-")
            if manifest.pair_id is not None:
                raise AddReportError("presentation pairs are not supported by add-report")
            if manifest.report.path != f"canonical/{slug}/report.md":
                raise AddReportError("report.path must match canonical/<slug>/report.md")
            _source_unchanged(source)
            # A sibling is external even if TMPDIR points inside the corpus.
            temporary = tempfile.TemporaryDirectory(prefix=".sloplab-stage-", dir=root.parent)
            stage_root = Path(temporary.name)
            stage = stage_root / "canonical" / slug
            stage.mkdir(parents=True)
            text = manifest_yaml(manifest)
            (stage / "report.md").write_bytes(source.content)
            (stage / "manifest.yaml").write_bytes(text.encode("utf-8"))
            staged = load_canonical_fixture(stage, stage_root)
            validation = ValidationResult(checked_canonical=1)
            validate_canonical_fixture(staged, validation)  # includes safety
            _require_ok(validation, "fixture validation")
            destination = root / "canonical" / slug
            preflight = _preflight(root, staged, destination)
            if _tree_digest(root) != before or _identity(root) != root_identity:
                raise AddReportError("corpus changed during preflight; prepare it again")
            prepared = PreparedReport(
                source,
                root,
                destination,
                stage,
                text,
                validation,
                preflight,
                before,
                root_identity,
                _tree_digest(stage),
                _state=state,
            )
        except (OSError, UnicodeError, FixtureError, ValidationError) as exc:
            raise AddReportError(f"cannot prepare fixture: {exc}") from exc
        yield prepared
    except BaseException as exc:
        active_error = exc
        raise
    finally:
        if temporary is not None:
            try:
                temporary.cleanup()
            except (OSError, KeyboardInterrupt) as cleanup:
                _cleanup_failed("stage", Path(temporary.name), cleanup, state, active_error)


@contextmanager
def _corpus_lock(root: Path, state: _CommitState) -> Iterator[None]:
    lock = root.parent / f".{root.name}.sloplab-add-report.lock"
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise AddReportError(
            f"another add-report transaction or a stale lock exists: {lock}; "
            "retry after it finishes; remove a stale lock only after checking no writer is running"
        ) from exc
    active_error: BaseException | None = None
    try:
        yield
    except BaseException as exc:
        active_error = exc
        raise
    finally:
        try:
            lock.rmdir()
        except (OSError, KeyboardInterrupt) as cleanup:
            _cleanup_failed("lock", lock, cleanup, state, active_error)


def _rollback(destination: Path, identity: tuple[int, int] | None) -> None:
    if identity is None or not os.path.lexists(destination):
        return
    if _identity(destination) != identity:
        raise AddReportError(
            f"rollback refused: destination ownership changed; inspect {destination}"
        )
    shutil.rmtree(destination)


def commit_add_report(prepared: PreparedReport, *, confirmed: bool = False) -> AddReportResult:
    """Commit only an explicitly approved, unchanged plan; revalidate and rollback.

    Sibling lock serializes cooperating writers. Native no-replace rename also
    refuses a target created between checking and publication. Cleanup handles
    ordinary exceptions and KeyboardInterrupt, never deletes a pre-existing target.
    After all final checks pass, lock/stage cleanup faults become result warnings,
    not transaction failures. Read cleanup_warnings after the preparation scope exits.
    """
    if confirmed is not True:
        raise AddReportError("explicit confirmation is required; corpus was not changed")
    if prepared.commit_result is not None:
        raise AddReportError(
            f"fixture already committed at {prepared.destination}; do not retry add-report"
        )
    root, destination = prepared.corpus_root, prepared.destination
    manifest = prepared.manifest
    slug = manifest.id.removeprefix("canonical-")
    if destination != root / "canonical" / slug:
        raise AddReportError("destination does not match the reviewed manifest")
    parent = destination.parent
    created_parent = False
    published = False
    pending_identity: tuple[int, int] | None = None
    try:
        with _corpus_lock(root, prepared._state):
            try:
                if (
                    _identity(root) != prepared._root_identity
                    or _tree_digest(root) != prepared._corpus_digest
                ):
                    raise AddReportError(
                        "corpus changed since preview; prepare and review it again"
                    )
                _source_unchanged(prepared.source)
                if _tree_digest(prepared.staged_directory) != prepared._stage_digest:
                    raise AddReportError("staged fixture changed since preview; prepare it again")
                if (
                    prepared.staged_directory / "report.md"
                ).read_bytes() != prepared.source.content or (
                    prepared.staged_directory / "manifest.yaml"
                ).read_bytes() != prepared.manifest_text.encode("utf-8"):
                    raise AddReportError("review snapshot no longer matches staged bytes")
                staged = load_canonical_fixture(
                    prepared.staged_directory, prepared.staged_directory.parents[1]
                )
                preflight = _preflight(root, staged, destination)
                if not parent.exists():
                    parent.mkdir()
                    created_parent = True
                _identity(parent)
                with tempfile.TemporaryDirectory(
                    prefix=".sloplab-commit-", dir=parent
                ) as temporary:
                    temporary_root = Path(temporary)
                    # Existing discovery prunes this wrapper during the brief write phase.
                    (temporary_root / SUITE_INDEX_NAME).write_bytes(b"")
                    pending = temporary_root / destination.name
                    pending.mkdir()
                    (pending / "report.md").write_bytes(prepared.source.content)
                    (pending / "manifest.yaml").write_bytes(prepared.manifest_text.encode("utf-8"))
                    pending_identity = _identity(pending)
                    publish_directory(pending, destination)
                    published = True
                canonical, derived = discover_fixtures(root)
                result = validate_corpus(canonical, derived, corpus_root=root)
                _require_ok(result, "post-write full corpus validation")
                if sum(f.fixture_id == prepared.manifest.id for f in canonical) != 1:
                    raise AddReportError(
                        "post-write discovery did not find exactly one new canonical ID"
                    )
                _source_unchanged(prepared.source)
                if _tree_digest(destination) != prepared._stage_digest:
                    raise AddReportError("published fixture bytes differ from the reviewed stage")
                if (
                    _tree_digest(
                        root, exclude=destination, omit_directory=parent if created_parent else None
                    )
                    != prepared._corpus_digest
                ):
                    raise AddReportError("existing corpus changed during commit; refusing success")
                committed = AddReportResult(
                    prepared.manifest.id,
                    destination,
                    destination / "report.md",
                    destination / "manifest.yaml",
                    preflight.checked_canonical - 1,
                    result,
                )
                # Commit point: all post-write checks have passed. Only lock/stage
                # release remains; cleanup-only faults must not undo/report a failed add.
                prepared._state.result = committed
                return committed
            except BaseException as exc:
                prepared._state.result = None
                # If interrupted immediately after the syscall but before the flag,
                # identify the just-published directory by its pre-rename inode.
                owned = published
                if (
                    not owned
                    and pending_identity is not None
                    and destination.is_dir()
                    and not destination.is_symlink()
                ):
                    owned = _identity(destination) == pending_identity
                try:
                    if owned:
                        _rollback(destination, pending_identity)
                    if created_parent:
                        parent.rmdir()  # never recursively delete someone else's data
                except (OSError, AddReportError) as cleanup:
                    raise AddReportError(
                        f"creation failed ({exc}); rollback incomplete: {cleanup}"
                    ) from exc
                raise
    except (OSError, UnicodeError, FixtureError, ValidationError) as exc:
        error = AddReportError(f"cannot commit fixture: {exc}")
        for note in getattr(exc, "__notes__", []):
            error.add_note(note)
        raise error from exc
