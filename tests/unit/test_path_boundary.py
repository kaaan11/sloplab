"""Direct contracts for untrusted paths and symlink-aware containment."""

from __future__ import annotations

from pathlib import Path

import pytest

from sloplab.path_boundary import PathBoundaryError, resolve_within_root


@pytest.mark.parametrize("path", ["../outside", "nested/../../outside"])
def test_parent_traversal_rejected(tmp_path: Path, path: str) -> None:
    with pytest.raises(PathBoundaryError, match="input escapes its allowed root"):
        resolve_within_root(tmp_path, path, label="input")


def test_absolute_path_rejected_even_inside_root(tmp_path: Path) -> None:
    with pytest.raises(PathBoundaryError, match="input must be relative"):
        resolve_within_root(tmp_path, tmp_path / "inside", label="input")


def test_symlink_outside_root_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(PathBoundaryError, match="escapes its allowed root"):
        resolve_within_root(root, "link/missing", label="input")


def test_symlink_inside_root_allowed(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (tmp_path / "link").symlink_to(target, target_is_directory=True)
    assert resolve_within_root(tmp_path, "link/leaf", label="input") == target / "leaf"


def test_missing_leaf_allowed(tmp_path: Path) -> None:
    expected = tmp_path / "missing" / "leaf"
    assert not expected.exists()
    assert resolve_within_root(tmp_path, "missing/leaf", label="input") == expected


@pytest.mark.parametrize("error", [OSError("unreadable"), RuntimeError("loop"), ValueError("bad")])
def test_resolution_errors_wrapped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def fail_resolve(self: Path) -> Path:
        raise error

    monkeypatch.setattr(Path, "resolve", fail_resolve)
    with pytest.raises(PathBoundaryError, match="input is not a valid path") as caught:
        resolve_within_root(tmp_path, "leaf", label="input")
    assert caught.value.__cause__ is error
