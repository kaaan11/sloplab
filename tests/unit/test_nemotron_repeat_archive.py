"""Recorded live results remain replayable offline after maintenance commits."""

from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import subprocess
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
    with pytest.raises(subprocess.CalledProcessError) as error:
        replay_module.replay(ARCHIVE, snapshot)
    assert "Input identities changed" in error.value.stderr
