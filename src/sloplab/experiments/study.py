"""Deterministic study runner: byte-identical results for commit + seed (V24)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sloplab.corpus.loader import discover_fixtures
from sloplab.evaluators.base import get_evaluator
from sloplab.experiments.config import DeterministicStudyConfig
from sloplab.experiments.runner import (
    ExperimentProvenance,
    current_commit_sha,
    sha256_file,
    sha256_text,
    utc_now_iso,
    write_run_bundle,
)
from sloplab.mutations.materialize import load_suite_config, materialize_suite
from sloplab.scoring.harness import build_cases, run_suite


@dataclass(frozen=True)
class StudyRunResult:
    out_dir: Path
    records_path: Path
    manifest_path: Path
    case_count: int


def resolve_against_anchors(path_str: str, anchors: list[Path]) -> Path:
    """Resolve ``path_str`` against the first anchor where it exists.

    Absolute paths pass through unchanged. Raises when nothing matches.
    """
    candidate = Path(path_str)
    if candidate.is_absolute():
        return candidate
    for anchor in anchors:
        resolved = anchor / candidate
        if resolved.exists():
            return resolved
    raise FileNotFoundError(
        f"path '{path_str}' does not exist relative to any of {[str(a) for a in anchors]}"
    )


def run_deterministic_study(
    config: DeterministicStudyConfig,
    study_config_path: Path,
    out_dir: Path,
) -> StudyRunResult:
    """Materialize the suite, evaluate all evaluators, write a reproducible bundle.

    Byte-identity contract: for a fixed repository commit, corpus, and seed, the
    ``records.jsonl`` file is byte-identical across runs. Wall-clock and machine
    details live only in ``manifest.json``.
    """
    anchors = [Path.cwd(), *study_config_path.absolute().parents]
    suite_yaml_path = resolve_against_anchors(config.suite.config_path, anchors)

    # 1. materialize the suite into the experiment output (deterministic).
    suite_config = load_suite_config(suite_yaml_path)
    corpus_root = resolve_against_anchors(config.suite.corpus_root, anchors)
    canonical, _derived = discover_fixtures(corpus_root)
    if not canonical:
        raise ValueError(f"no canonical fixtures under '{corpus_root}'")
    materialize_suite(
        suite_config,
        canonical,
        out_dir,
        corpus_root_resolved=corpus_root.resolve(),
    )

    # 2. evaluate.
    index_path = out_dir / "suite-index.jsonl"
    cases = build_cases(index_path, corpus_root, out_dir)

    record_lines: list[str] = []
    evaluator_hashes: dict[str, str] = {}
    evaluator_infos: list[dict[str, str]] = []
    for spec in config.evaluators:
        evaluator = get_evaluator(spec.name)
        records = run_suite(evaluator, cases)
        for record in records:
            record_lines.append(record.model_dump_json())
        evaluator_infos.append({"name": evaluator.name, "version": evaluator.version})
        evaluator_hashes[evaluator.name] = sha256_text(json.dumps(spec.config, sort_keys=True))

    records_jsonl = "".join(line + "\n" for line in record_lines)

    # 3. provenance manifest.
    provenance = ExperimentProvenance(
        experiment_name=config.name,
        config_hash=sha256_text(json.dumps(config.model_dump(), sort_keys=True)),
        commit_sha=current_commit_sha(study_config_path.absolute().parent),
        suite_hash=sha256_file(index_path),
        corpus_root=str(corpus_root),
        base_seed=config.base_seed,
        repeat_index=config.repeat_index,
        evaluators=evaluator_infos,
        evaluator_config_hashes=evaluator_hashes,
        started_at=utc_now_iso(),
        finished_at=utc_now_iso(),
    )
    manifest_path, records_path = write_run_bundle(out_dir, provenance, records_jsonl)

    return StudyRunResult(
        out_dir=out_dir,
        records_path=records_path,
        manifest_path=manifest_path,
        case_count=len(cases),
    )
