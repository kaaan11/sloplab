"""Resolve untrusted repository paths without crossing their declared root."""

from __future__ import annotations

from pathlib import Path


class PathBoundaryError(ValueError):
    """A path supplied by repository data escapes its allowed filesystem root."""


def resolve_within_root(root: Path, path: str | Path, *, label: str) -> Path:
    """Resolve a relative path and refuse absolute or root-escaping targets.

    Path.resolve() follows existing symlinks, so a path that is lexically
    inside root but resolves through a symlink outside it is rejected too.
    Missing leaf paths are still allowed here; the caller keeps ownership of
    existence/type validation.
    """
    root_resolved = root.resolve()
    candidate = Path(path)
    if candidate.is_absolute():
        raise PathBoundaryError(
            f"{label} must be relative to its root; absolute path is not allowed: {path!s}"
        )
    resolved = (root_resolved / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise PathBoundaryError(
            f"{label} escapes its allowed root {root_resolved}: {path!s}"
        ) from exc
    return resolved
