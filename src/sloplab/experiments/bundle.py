"""Bundle completion markers and the strict reader boundary (E3a).

New-schema result bundles (``study``, ``llm-pilot``) open publication with an
in-progress marker. After all data files exist, ``completion.json`` records the
bundle kind and SHA-256 of every data file; removing the in-progress marker is
the final publish transition. A run therefore never looks complete before its
required files and hashes are in place. The strict reader
(:func:`verify_bundle`) rejects active/interrupted, missing, stale, mixed, or
hash-broken bundles. Marker-less historical directories are recognized as
``legacy`` (see :func:`classify_bundle`) and consumed only through the explicit
legacy path — never auto-converted, never granted new-schema guarantees.

Staging/publish note: writers hold an exclusive process lock across dispatch,
data writes, analysis, and completion. Each progress marker carries its owner's
token; only that owner may finish publication. The persistent lock file is never
unlinked, and neither it nor the progress token is part of bundle identity.
Writers publish in place. A crash between files leaves
the in-progress marker in place, which every reader rejects even if a prior or
new completion file is also present. Same-filesystem renames are atomic per
file only; no whole-bundle atomicity is claimed.

The marker itself is fully deterministic (schema, kind, sorted file map — no
timestamps), so byte-identity checks across runs are unaffected apart from
the marker's own presence and the hashed wall-clock bytes it covers.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, BinaryIO
from uuid import uuid4

#: Marker file published last in every new-schema bundle directory.
COMPLETION_FILE_NAME = "completion.json"

#: In-progress marker: written before any output mutation or model dispatch,
#: removed only after the completion marker is fully written. Its presence
#: means "publishing or interrupted — do not consume", even when a completion
#: file is also present. Never counted as bundle data.
IN_PROGRESS_FILE_NAME = "publish-in-progress.json"

#: Persistent inode: never unlink it, even after a successful publication.
PUBLISH_LOCK_FILE_NAME = ".publish.lock"

#: Version of the completion envelope. Bump when the document shape changes;
#: the strict reader rejects unknown versions instead of guessing.
BUNDLE_SCHEMA_VERSION = 1

#: Bundle kinds published with a completion marker.
BUNDLE_KINDS = ("study", "llm-pilot")

#: Minimum files each kind must contain (beyond the exact recorded set).
KIND_REQUIRED_FILES: dict[str, frozenset[str]] = {
    "study": frozenset(
        {
            "manifest.json",
            "records.jsonl",
            "suite-index.jsonl",
            "input-identity.json",
            "execution-recipe.json",
            "analysis.json",
        }
    ),
    "llm-pilot": frozenset({"manifest.json", "records.jsonl", "outcomes.jsonl"}),
}

#: Files that mark a marker-less directory as legacy (never auto-converted).
LEGACY_SHAPE_FILES = frozenset(
    {"manifest.json", "records.jsonl", "outcomes.jsonl", "run.jsonl", "suite-index.jsonl"}
)


class BundleError(ValueError):
    """A bundle directory is not a verifiable complete new-schema bundle."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bundle_tree(out_dir: Path) -> dict[str, str]:
    """Map every regular bundle file (relative path -> SHA-256).

    Protocol-internal files (completion, progress, and process lock) are never
    bundle data. Every other file present at publish time is covered.
    """
    tree: dict[str, str] = {}
    for path in sorted(p for p in out_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(out_dir).as_posix()
        if rel in (COMPLETION_FILE_NAME, IN_PROGRESS_FILE_NAME, PUBLISH_LOCK_FILE_NAME):
            continue
        tree[rel] = _sha256_file(path)
    return tree


def _completion_document(kind: str, tree: dict[str, str]) -> dict[str, Any]:
    return {
        "bundle_schema": BUNDLE_SCHEMA_VERSION,
        "kind": kind,
        "files": dict(sorted(tree.items())),
    }


def write_completion(out_dir: Path, *, kind: str) -> Path:
    """Publish the completion marker for ``out_dir``; call only after all files.

    Records the SHA-256 of every file currently in the directory (except the
    marker itself). The document is deterministic: no timestamps, sorted keys.
    Returns the marker path.
    """
    if kind not in BUNDLE_KINDS:
        raise BundleError(f"unknown bundle kind {kind!r}")
    missing = KIND_REQUIRED_FILES[kind] - {
        p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*") if p.is_file()
    }
    if missing:
        raise BundleError(f"cannot complete {kind} bundle; missing {sorted(missing)}")
    marker = out_dir / COMPLETION_FILE_NAME
    document = _completion_document(kind, _bundle_tree(out_dir))
    marker.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return marker


@dataclass
class Publication:
    """Process-bound ownership of a single publish cycle; close on every exit."""

    out_dir: Path
    kind: str
    token: str
    pid: int
    _lock: BinaryIO

    def __enter__(self) -> Publication:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Release ownership, preserving any interrupted marker for readers."""
        self._lock.close()

    def check(self, out_dir: Path, *, kind: str) -> None:
        """Refuse stale, foreign-process, or replaced publication ownership."""
        if (
            self._lock.closed
            or self.pid != os.getpid()
            or self.out_dir != out_dir.resolve()
            or self.kind != kind
        ):
            raise BundleError(f"{out_dir}: publication ownership mismatch")
        try:
            progress = json.loads((out_dir / IN_PROGRESS_FILE_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BundleError(
                f"{out_dir}: publication ownership marker missing or invalid"
            ) from exc
        if not isinstance(progress, dict) or progress.get("token") != self.token:
            raise BundleError(f"{out_dir}: publication ownership mismatch")


def begin_publish(out_dir: Path, *, kind: str) -> Publication:
    """Acquire exclusive process ownership before any mutation or dispatch.

    Use as a context manager across the entire publication, including analysis.
    A second publisher fails immediately without changing bundle files. A dead
    publisher releases the OS lock but leaves its progress marker; a subsequent
    owner may replace that interrupted marker only after acquiring the lock.
    """
    if kind not in BUNDLE_KINDS:
        raise BundleError(f"unknown bundle kind {kind!r}")
    out_dir.mkdir(parents=True, exist_ok=True)
    lock = (out_dir / PUBLISH_LOCK_FILE_NAME).open("a+b")
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BundleError(
                f"{out_dir}: another publisher is active; choose a different --out directory"
            ) from exc
        publication = Publication(out_dir.resolve(), kind, uuid4().hex, os.getpid(), lock)
        progress = out_dir / IN_PROGRESS_FILE_NAME
        progress.write_text(
            json.dumps(
                {
                    "bundle_schema": BUNDLE_SCHEMA_VERSION,
                    "kind": kind,
                    "state": "in-progress",
                    "token": publication.token,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        # Progress precedes retiring completion, avoiding a legacy-shaped gap.
        (out_dir / COMPLETION_FILE_NAME).unlink(missing_ok=True)
        return publication
    except BaseException:
        lock.close()
        raise


def finish_publish(out_dir: Path, *, kind: str, publication: Publication | None = None) -> Path:
    """Write completion and remove only this owner's marker, under its lock."""
    if publication is None:
        raise BundleError(f"{out_dir}: publication ownership required")
    publication.check(out_dir, kind=kind)
    marker = write_completion(out_dir, kind=kind)
    publication.check(out_dir, kind=kind)
    (out_dir / IN_PROGRESS_FILE_NAME).unlink()
    return marker


@contextmanager
def _reader_lock(out_dir: Path) -> Iterator[None]:
    """Keep a complete bundle stable while verifying; never create reader files."""
    try:
        lock = (out_dir / PUBLISH_LOCK_FILE_NAME).open("rb")
    except FileNotFoundError:
        yield
        return
    with lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BundleError(f"{out_dir}: publish in progress; not consumable") from exc
        yield


def read_completion(out_dir: Path) -> dict[str, Any]:
    """Parse the marker, checking only its envelope (not the bundle files)."""
    marker = out_dir / COMPLETION_FILE_NAME
    if not marker.is_file():
        raise BundleError(f"{out_dir}: no {COMPLETION_FILE_NAME} (legacy or incomplete)")
    try:
        document = json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BundleError(f"{marker}: unparsable completion marker: {exc}") from exc
    if not isinstance(document, dict):
        raise BundleError(f"{marker}: completion marker is not an object")
    if document.get("bundle_schema") != BUNDLE_SCHEMA_VERSION:
        raise BundleError(f"{marker}: unsupported bundle_schema {document.get('bundle_schema')!r}")
    if document.get("kind") not in BUNDLE_KINDS:
        raise BundleError(f"{marker}: unknown bundle kind {document.get('kind')!r}")
    files = document.get("files")
    if not isinstance(files, dict) or not files:
        raise BundleError(f"{marker}: completion marker carries no file map")
    return document


def verify_bundle(out_dir: Path, *, kind: str) -> dict[str, Any]:
    """Strictly verify ``out_dir`` as a complete ``kind`` bundle.

    The in-progress marker is checked before the completion marker: a
    publish (or an interrupted one) in flight is refused even when a
    completion file is present and would otherwise verify. Then requires
    the marker, the declared kind, the kind's required files, an exact
    file set (no missing, no unlisted extras), and a matching SHA-256 for
    every listed file. Returns the completion document on success; raises
    :class:`BundleError` otherwise.
    """
    with _reader_lock(out_dir):
        return _verify_bundle(out_dir, kind=kind)


def _verify_bundle(out_dir: Path, *, kind: str) -> dict[str, Any]:
    if kind not in BUNDLE_KINDS:
        raise BundleError(f"unknown bundle kind {kind!r}")
    if (out_dir / IN_PROGRESS_FILE_NAME).is_file():
        raise BundleError(f"{out_dir}: publish in progress or interrupted; not consumable")
    document = read_completion(out_dir)
    if document["kind"] != kind:
        raise BundleError(f"{out_dir}: bundle kind is {document['kind']!r}, expected {kind!r}")
    recorded: dict[str, str] = document["files"]
    missing_required = KIND_REQUIRED_FILES[kind] - set(recorded)
    if missing_required:
        raise BundleError(f"{out_dir}: marker omits required {sorted(missing_required)}")
    actual = _bundle_tree(out_dir)
    missing = sorted(set(recorded) - set(actual))
    if missing:
        raise BundleError(f"{out_dir}: missing bundle files {missing}")
    extra = sorted(set(actual) - set(recorded))
    if extra:
        raise BundleError(f"{out_dir}: unlisted extra files {extra}")
    broken = sorted(name for name in recorded if recorded[name] != actual[name])
    if broken:
        raise BundleError(f"{out_dir}: hash mismatch for {broken}")
    return document


def open_result_dir(path: Path, *, purpose: str) -> str:
    """Gate a result-directory read on the integrity boundary (E3b).

    ``path`` is a bundle directory or a file inside one (the parent is
    used). Returns ``"complete"`` after strict verification, or
    ``"legacy"`` for marker-less historical bundles, which callers consume
    in explicit legacy mode without new-schema guarantees. An in-progress
    (or interrupted) publish is refused even with a completion file
    present. Raises :class:`BundleError` for broken markers and
    unrecognizable directories: there is no silent bypass.
    """
    out_dir = path if path.is_dir() else path.parent
    if (out_dir / IN_PROGRESS_FILE_NAME).is_file():
        raise BundleError(f"{out_dir}: publish in progress or interrupted; not consumable")
    marker = out_dir / COMPLETION_FILE_NAME
    if marker.is_file():
        document = read_completion(out_dir)
        verify_bundle(out_dir, kind=document["kind"])
        return "complete"
    names = {p.name for p in out_dir.rglob("*") if p.is_file()} if out_dir.is_dir() else set()
    if names & LEGACY_SHAPE_FILES:
        return "legacy"
    raise BundleError(f"{path}: no verifiable bundle for {purpose} (incomplete or unknown)")


def classify_bundle(out_dir: Path) -> str:
    """Recognize a bundle directory without fully consuming it.

    Returns ``"complete"`` (no in-progress marker, marker present and
    verifying), ``"incomplete"`` (in-progress present, marker present but
    broken, or nothing recognizable), or ``"legacy"`` (no in-progress
    marker, no completion marker, but legacy-shaped files: consumed only
    through the explicit legacy path). Classification is state-based, never
    filename-heuristic alone: an in-progress publish is ``"incomplete"``
    even when a completion file sits next to it.
    """
    if (out_dir / IN_PROGRESS_FILE_NAME).is_file():
        return "incomplete"
    marker = out_dir / COMPLETION_FILE_NAME
    if marker.is_file():
        try:
            document = read_completion(out_dir)
        except BundleError:
            return "incomplete"
        try:
            verify_bundle(out_dir, kind=document["kind"])
        except BundleError:
            return "incomplete"
        return "complete"
    if not out_dir.is_dir():
        return "incomplete"
    names = {p.name for p in out_dir.rglob("*") if p.is_file()}
    if names & LEGACY_SHAPE_FILES:
        return "legacy"
    return "incomplete"
