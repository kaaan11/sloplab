"""Filesystem path containment helpers for untrusted document references."""

from __future__ import annotations

from pathlib import Path


def resolve_within(root: Path, value: str | Path, *, purpose: str) -> Path:
    """Resolve a relative path and require its final target to stay under root.

    Absolute paths are rejected even when they happen to point inside the root.
    Path.resolve also follows existing symlinks, so links that escape the
    boundary are refused before callers open the target.
    """
    root_resolved = root.resolve()
    candidate = Path(value)
    if candidate.is_absolute():
        raise ValueError(f"{purpose} must be relative to root '{root_resolved}'")
    resolved = (root_resolved / candidate).resolve()
    if not resolved.is_relative_to(root_resolved):
        raise ValueError(f"{purpose} escapes root '{root_resolved}': {value}")
    return resolved
