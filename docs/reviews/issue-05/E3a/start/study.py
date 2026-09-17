"""Deterministic study runner: byte-identical results for commit + seed (V24)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sloplab.corpus.loader import discover_fixtures
from sloplab.evaluators.base import get_evaluator
from sloplab.experiments.config import DeterministicStudyConfig
from sloplab.experiments.input_identity import build_input_identity, write_input_identity
from sloplab.experiments.resolved_recipe import (
    ResolvedRecipe,
    build_execution_recipe,
    resolve_recipe,
    write_execution_recipe,
)
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


class StudyConfigError(ValueError):
    """A deterministic study config requests behavior the runner does not apply."""


def preflight_study_config(config: DeterministicStudyConfig) -> None:
    """Reject unsupported settings before any corpus/evaluation/output side effect.

    Supported today: empty per-evaluator ``config`` mappings, registered evaluator
    names, ``analysis.paired_comparison``/``analysis.error_taxonomy`` set to True,
    and all ``provenance.record_*`` flags set to True. Anything else fails here so
    no materialization, evaluation, or file write starts. All evaluator names are
    resolved up front (never lazily inside the evaluation loop).
    """
    for index, spec in enumerate(config.evaluators):
        if spec.config:
            raise StudyConfigError(
                f"study '{config.name}': evaluator '{spec.name}' sets "
                f"evaluators[{index}].config, which the deterministic study "
                "runner records but does not apply; use an empty mapping"
            )
    for spec in config.evaluators:
        try:
            get_evaluator(spec.name)
        except KeyError as exc:
            raise StudyConfigError(f"study '{config.name}': {exc}") from exc
    if not config.analysis.paired_comparison:
        raise StudyConfigError(
            f"study '{config.name}': analysis.paired_comparison=false is not "
            "supported by the deterministic study runner"
        )
    if not config.analysis.error_taxonomy:
        raise StudyConfigError(
            f"study '{config.name}': analysis.error_taxonomy=false is not "
            "supported by the deterministic study runner"
        )
    for field in ("record_commit_sha", "record_suite_hash", "record_evaluator_config_hash"):
        if not getattr(config.provenance, field):
            raise StudyConfigError(
                f"study '{config.name}': provenance.{field}=false is not "
                "supported by the deterministic study runner"
            )


@dataclass(frozen=True)
class StudyRunResult:
    out_dir: Path
    records_path: Path
    manifest_path: Path
    case_count: int
    recipe: ResolvedRecipe
    experiment_name: str


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
    # Own the validated inputs: callers can retain and mutate their models while
    # materialization/evaluation runs. Provenance must describe this copy too.
    config = config.model_copy(deep=True)
    preflight_study_config(config)
    anchors = [Path.cwd(), *study_config_path.absolute().parents]
    suite_yaml_path = resolve_against_anchors(config.suite.config_path, anchors)

    # 1. materialize the suite into the experiment output (deterministic).
    suite_config = load_suite_config(suite_yaml_path).model_copy(deep=True)
    corpus_root = resolve_against_anchors(config.suite.corpus_root, anchors)
    canonical, _derived = discover_fixtures(corpus_root)
    if not canonical:
        raise ValueError(f"no canonical fixtures under '{corpus_root}'")

    # Resolution boundary: freeze the effective settings once, from the same
    # loaded objects the run below consumes. The suite file is not re-read and
    # evaluator names are not re-resolved in the evaluation loop.
    recipe = resolve_recipe(
        config,
        suite_config,
        suite_config_path=suite_yaml_path,
        corpus_root=corpus_root,
        study_config_dir=study_config_path.absolute().parent,
    )
    materialize_suite(
        suite_config,
        canonical,
        out_dir,
        corpus_root_resolved=corpus_root.resolve(),
    )

    # 2. evaluate.
    index_path = out_dir / "suite-index.jsonl"
    cases = build_cases(index_path, corpus_root, out_dir)

    # 2. input identity from the same snapshots, before any evaluator runs.
    # Written once here (never regenerated from mutable sources at the end),
    # so the file binds exactly the inputs the evaluators below will see.
    identity = build_input_identity(cases)
    write_input_identity(out_dir, identity)
    write_execution_recipe(
        out_dir,
        build_execution_recipe(
            recipe,
            inputs_hash=identity["inputs_hash"],
            selection_hash=identity["selection_hash"],
        ),
    )

    record_lines: list[str] = []
    evaluator_hashes: dict[str, str] = {}
    evaluator_infos: list[dict[str, str]] = []
    for spec, evaluator in zip(recipe.evaluators, recipe.instances, strict=True):
        records = run_suite(evaluator, cases)
        for record in records:
            record_lines.append(record.model_dump_json())
        evaluator_infos.append({"name": spec.name, "version": spec.version})
        evaluator_hashes[spec.name] = sha256_text(json.dumps(dict(spec.config), sort_keys=True))

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
        recipe=recipe,
        experiment_name=config.name,
    )
