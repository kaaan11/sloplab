"""Bundle completion markers and the strict reader boundary (E3a).

New-schema result bundles (``study``, ``llm-pilot``) are published with a
``completion.json`` marker written LAST. The marker carries the bundle kind
and the SHA-256 of every other file in the bundle directory, so a run never
looks complete before its required files and hashes are in place. The strict
reader (:func:`verify_bundle`) rejects missing, stale, mixed, or hash-broken
bundles; marker-less directories are recognized as ``legacy`` (see
:func:`classify_bundle`) and consumed only through the explicit legacy path —
never auto-converted, never granted new-schema guarantees.

Staging/publish note: writers publish in place and the marker is written
last. A crash between files leaves a marker-less (or hash-mismatched)
directory that the strict reader rejects. Same-filesystem renames are atomic
per file only; no whole-bundle atomicity is claimed.

The marker itself is fully deterministic (schema, kind, sorted file map — no
timestamps), so byte-identity checks across runs are unaffected apart from
the marker's own presence and the hashed wall-clock bytes it covers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

#: Marker file published last in every new-schema bundle directory.
COMPLETION_FILE_NAME = "completion.json"

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
    """Map every regular bundle file (relative path -> SHA-256), except the marker."""
    tree: dict[str, str] = {}
    for path in sorted(p for p in out_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(out_dir).as_posix()
        if rel == COMPLETION_FILE_NAME:
            continue
        tree[rel] = _sha256_file(path)
    return tree


def _completion_document(kind: str, tree: dict[str, str]) -> dict[str, Any]:
    return {
        "bundle_schema": BUNDLE_SCHEMA_VERSION,
        "kind": kind,
        "files": dict(sorted(tree.items())),
    }


def invalidate_completion(out_dir: Path) -> None:
    """Remove a prior publication marker before rewriting a bundle in place."""
    (out_dir / COMPLETION_FILE_NAME).unlink(missing_ok=True)


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

    Requires the marker, the declared kind, the kind's required files, an
    exact file set (no missing, no unlisted extras), and a matching SHA-256
    for every listed file. Returns the completion document on success; raises
    :class:`BundleError` otherwise.
    """
    if kind not in BUNDLE_KINDS:
        raise BundleError(f"unknown bundle kind {kind!r}")
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
    in explicit legacy mode without new-schema guarantees. Raises
    :class:`BundleError` for broken markers and unrecognizable directories:
    there is no silent bypass.
    """
    out_dir = path if path.is_dir() else path.parent
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

    Returns ``"complete"`` (marker present and verifying), ``"incomplete"``
    (marker present but broken, or nothing recognizable), or ``"legacy"`` (no
    marker but legacy-shaped files: consumed only through the explicit legacy
    path). An interrupted new publish
    without a marker classifies as ``"legacy"``-shaped and is equally
    rejected by the strict reader.
    """
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
