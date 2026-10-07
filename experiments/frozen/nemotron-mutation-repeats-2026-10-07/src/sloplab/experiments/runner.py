"""Experiment infrastructure: versioned configs, provenance, and result storage."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from sloplab.corpus.loader import format_validation_error
from sloplab.experiments.config import DeterministicStudyConfig, LLMPilotConfig
from sloplab.models.run import RunMetadata

EXPERIMENT_SCHEMA_VERSION = 2


def load_study_config(path: Path) -> DeterministicStudyConfig:
    from pydantic import ValidationError

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        return DeterministicStudyConfig.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(
            f"{path}: deterministic study config invalid\n{format_validation_error(exc)}"
        ) from exc


def load_pilot_config(path: Path) -> LLMPilotConfig:
    from pydantic import ValidationError

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        return LLMPilotConfig.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(
            f"{path}: LLM pilot config invalid\n{format_validation_error(exc)}"
        ) from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def current_commit_sha(repo_root: Path) -> str | None:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


@dataclass(frozen=True)
class ExperimentProvenance:
    """Full provenance block recorded alongside every experiment run (V24)."""

    experiment_name: str
    config_hash: str
    commit_sha: str | None
    suite_hash: str
    corpus_root: str
    base_seed: int
    repeat_index: int
    evaluators: list[dict[str, str]]
    evaluator_config_hashes: dict[str, str]
    prompt_hash: str | None = None
    model: str | None = None
    endpoint_host: str | None = None  # host only; never full URL/keys
    started_at: str = ""
    finished_at: str = ""
    request_count: int = 0
    error_count: int = 0
    timeout_count: int = 0

    def to_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True, indent=2)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def write_run_bundle(
    out_dir: Path,
    provenance: ExperimentProvenance,
    records_jsonl: str,
) -> tuple[Path, Path]:
    """Write manifest.jsonl (provenance) + records.jsonl for one experiment run.

    ``records_jsonl`` must be fully determined by inputs (commit + seed + corpus);
    wall-clock lives only in the manifest so byte-identity checks compare records.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(provenance.to_json() + "\n", encoding="utf-8")
    records_path = out_dir / "records.jsonl"
    records_path.write_text(records_jsonl, encoding="utf-8")
    return manifest_path, records_path


_ = RunMetadata, Any
