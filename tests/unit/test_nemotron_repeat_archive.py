"""Recorded live results remain replayable offline after maintenance commits."""

from __future__ import annotations

import hashlib
import importlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "experiments/results/llm-pilot/2026-10-07"
ARCHIVE = BASE / "nemotron-mutation-repeats-01"
SNAPSHOT = ROOT / "experiments/frozen/nemotron-mutation-repeats-2026-10-07"


@pytest.fixture
def replay_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.syspath_prepend(str(ROOT / "experiments/scripts"))
    return importlib.import_module("replay_nemotron_mutation_repeats")


def test_historical_replay_uses_frozen_sources_and_matches_saved_summary(
    replay_module: Any,
) -> None:
    result = replay_module.replay(ARCHIVE, SNAPSHOT)
    assert result == json.loads((ARCHIVE / "summary.json").read_text())
    assert result["physical_requests"] == 891
    assert result["valid"] == 890
    assert result["stability"]["mutated"]["complete"] == 236
    assert result["stability"]["mutated"]["changed"] == 19


def test_changed_frozen_source_is_rejected(replay_module: Any, tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    shutil.copytree(SNAPSHOT, snapshot)
    (snapshot / "src/sloplab/tui/app.py").write_text("changed")
    with pytest.raises(ValueError, match="Frozen source/input changed"):
        replay_module.replay(ARCHIVE, snapshot)


def test_rehashed_post_study_input_manifest_cannot_override_registered_identity(
    replay_module: Any, tmp_path: Path
) -> None:
    snapshot = tmp_path / "snapshot"
    shutil.copytree(SNAPSHOT, snapshot)
    path = snapshot / "corpus/canonical/authz-001/report.md"
    path.write_text(path.read_text() + "\nA changed report.\n")
    manifest_path = snapshot / "snapshot-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["input_files"][str(path.relative_to(snapshot))] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="Input identities changed"):
        replay_module.replay(ARCHIVE, snapshot)


def test_child_verifier_stderr_reaches_caller(replay_module: Any, tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    shutil.copytree(SNAPSHOT, snapshot)
    path = snapshot / "corpus/canonical/authz-001/report.md"
    path.write_text(path.read_text() + "\nA changed report.\n")
    manifest_path = snapshot / "snapshot-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["input_files"][str(path.relative_to(snapshot))] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError) as error:
        replay_module.replay(ARCHIVE, snapshot)
    assert "exit status" in str(error.value)
    assert "ValueError: Input identities changed" in str(error.value)


def test_untracked_junk_is_ignored_but_real_extra_file_is_rejected(
    replay_module: Any, tmp_path: Path
) -> None:
    snapshot = tmp_path / "snapshot"
    shutil.copytree(SNAPSHOT, snapshot)
    (snapshot / "src/sloplab/__pycache__").mkdir()
    (snapshot / "src/sloplab/__pycache__/x.cpython-312.pyc").write_bytes(b"junk")
    (snapshot / ".DS_Store").write_bytes(b"junk")
    (snapshot / "src/sloplab/.models.py.swp").write_bytes(b"junk")
    assert replay_module.source_files(ARCHIVE, snapshot)
    (snapshot / "src/sloplab/extra.py").write_text("print('extra')")
    with pytest.raises(ValueError, match="Snapshot inventory changed"):
        replay_module.source_files(ARCHIVE, snapshot)


def test_replay_rejects_dependency_version_mismatch(
    replay_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = replay_module.metadata.version

    def fake(name: str) -> str:
        return "0.0.0" if name == "pydantic" else str(real(name))

    monkeypatch.setattr(replay_module.metadata, "version", fake)
    with pytest.raises(RuntimeError, match=r"pydantic.*expected 2\.13\.4.*installed 0\.0\.0"):
        replay_module.replay(ARCHIVE, SNAPSHOT)


def test_replay_reports_missing_dependency(
    replay_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = replay_module.metadata.version

    def fake(name: str) -> str:
        if name == "pydantic":
            raise replay_module.metadata.PackageNotFoundError(name)
        return str(real(name))

    monkeypatch.setattr(replay_module.metadata, "version", fake)
    with pytest.raises(RuntimeError, match=r"pydantic.*expected 2\.13\.4.*installed missing"):
        replay_module.replay(ARCHIVE, SNAPSHOT)
