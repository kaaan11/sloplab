"""Resolved effective recipe for deterministic studies (E1e).

Freezes, at one resolution boundary, the settings the run will actually apply:
the loaded suite's generation inputs, the resolved evaluator objects, and the
analysis options. The frozen copy (not the mutable originals) feeds
materialization input, the evaluation loop, the CLI analysis, and the recorded
``execution-recipe.json`` file, so recorded settings cannot drift from used ones.
"""

from __future__ import annotations

import hashlib
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sloplab import __version__ as _sloplab_version
from sloplab.evaluators.base import Evaluator, get_evaluator
from sloplab.experiments.config import DeterministicStudyConfig
from sloplab.experiments.input_identity import canonical_json_bytes, tagged_digest
from sloplab.models.suite import SuiteConfig

RECIPE_SCHEMA_VERSION = 1
RECIPE_FILE_NAME = "execution-recipe.json"
RECIPE_DOMAIN = "sloplab.recipe"


@dataclass(frozen=True)
class ResolvedPolicy:
    """One suite policy group with its operator list in configured order."""

    group: str
    variants_per_fixture: int
    operators: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedEvaluator:
    """One evaluator entry: real name/version plus the accepted config copy."""

    name: str
    version: str
    config: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ResolvedAnalysis:
    """Applied analysis options; bootstrap seed is the study seed, not the suite's."""

    bootstrap_seed: int
    bootstrap_resamples: int
    bootstrap_ci: float
    paired_comparison: bool
    error_taxonomy: bool


@dataclass(frozen=True)
class ResolvedProvenanceOptions:
    """Applied provenance flags."""

    record_commit_sha: bool
    record_suite_hash: bool
    record_evaluator_config_hash: bool


@dataclass(frozen=True)
class ResolvedLocations:
    """Resolved absolute paths; carried openly, never hashed into identities."""

    suite_config_path: str
    corpus_root: str


@dataclass(frozen=True)
class ResolvedCodeEnv:
    """Code/environment metadata for the recipe file; excluded from identities.

    A dirty HEAD is recorded as-is and is not presented as a full code identity;
    no source closure, shell dump, or credential is captured here.
    """

    head: str | None
    dirty: bool | None
    python_implementation: str
    python_version: str
    sloplab_version: str
    uv_lock_sha256: str | None


@dataclass(frozen=True)
class ResolvedRecipe:
    """Frozen effective settings plus the resolved evaluator objects.

    Scalar/tuple fields only (no shared mutable containers); ``instances`` holds
    the exact objects the evaluation loop must use instead of re-resolving names.
    No thread/process safety is claimed for those objects.
    """

    generation_seed: int
    include_canonical_cases: bool
    policies: tuple[ResolvedPolicy, ...]
    suite_name: str
    evaluators: tuple[ResolvedEvaluator, ...]
    instances: tuple[Evaluator, ...] = field(compare=False)
    analysis: ResolvedAnalysis | None = None
    provenance: ResolvedProvenanceOptions | None = None
    repeat_index: int = 0
    locations: ResolvedLocations | None = None
    code_env: ResolvedCodeEnv | None = None


def _find_uv_lock(start: Path) -> Path | None:
    for parent in [start, *start.parents]:
        candidate = parent / "uv.lock"
        if candidate.is_file():
            return candidate
    return None


def _sha256_file(path: Path) -> str | None:
    try:
        digest_blocks = path.read_bytes()
    except OSError:
        return None
    return hashlib.sha256(digest_blocks).hexdigest()


def _git_state(root: Path) -> tuple[str | None, bool | None]:
    """HEAD sha and dirty flag for ``root``; (None, None) when git is unavailable."""
    import subprocess

    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=5
        )
        status = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    if head.returncode != 0 or status.returncode != 0:
        return None, None
    return (head.stdout.strip() or None, bool(status.stdout.strip()))


def resolve_recipe(
    config: DeterministicStudyConfig,
    suite_config: SuiteConfig,
    *,
    suite_config_path: Path,
    corpus_root: Path,
    study_config_dir: Path,
) -> ResolvedRecipe:
    """Freeze the effective settings once; call before any materialization/evaluation.

    Reads the loaded ``suite_config`` object (the same object the materializer
    receives; the file is not re-read) and resolves each evaluator name exactly
    once. Absolute paths enter ``locations`` only, never the hashed sections.
    """
    instances: list[Evaluator] = [get_evaluator(spec.name) for spec in config.evaluators]
    evaluators = tuple(
        ResolvedEvaluator(
            name=instance.name,
            version=instance.version,
            config=tuple(sorted(spec.config.items())),
        )
        for spec, instance in zip(config.evaluators, instances, strict=True)
    )
    policies = tuple(
        ResolvedPolicy(
            group=group,
            variants_per_fixture=policy.variants_per_fixture,
            operators=tuple(policy.operators),
        )
        for group, policy in suite_config.policies.items()
    )
    head, dirty = _git_state(study_config_dir)
    lock = _find_uv_lock(study_config_dir)
    return ResolvedRecipe(
        generation_seed=suite_config.base_seed,
        include_canonical_cases=suite_config.include_canonical_cases,
        policies=policies,
        suite_name=suite_config.name,
        evaluators=evaluators,
        instances=tuple(instances),
        analysis=ResolvedAnalysis(
            bootstrap_seed=config.base_seed,
            bootstrap_resamples=config.analysis.bootstrap_resamples,
            bootstrap_ci=config.analysis.bootstrap_ci,
            paired_comparison=config.analysis.paired_comparison,
            error_taxonomy=config.analysis.error_taxonomy,
        ),
        provenance=ResolvedProvenanceOptions(
            record_commit_sha=config.provenance.record_commit_sha,
            record_suite_hash=config.provenance.record_suite_hash,
            record_evaluator_config_hash=config.provenance.record_evaluator_config_hash,
        ),
        repeat_index=config.repeat_index,
        locations=ResolvedLocations(
            suite_config_path=str(suite_config_path),
            corpus_root=str(corpus_root),
        ),
        code_env=ResolvedCodeEnv(
            head=head,
            dirty=dirty,
            python_implementation=platform.python_implementation(),
            python_version=platform.python_version(),
            sloplab_version=_sloplab_version,
            uv_lock_sha256=_sha256_file(lock) if lock is not None else None,
        ),
    )


def _generation_object(recipe: ResolvedRecipe) -> dict[str, Any]:
    return {
        "base_seed": recipe.generation_seed,
        "include_canonical_cases": recipe.include_canonical_cases,
        "policies": {
            policy.group: {
                "variants_per_fixture": policy.variants_per_fixture,
                "operators": list(policy.operators),
            }
            for policy in recipe.policies
        },
        "suite_name": recipe.suite_name,
    }


def _evaluation_object(recipe: ResolvedRecipe) -> dict[str, Any]:
    return {
        "evaluators": [
            {"name": entry.name, "version": entry.version, "config": dict(entry.config)}
            for entry in recipe.evaluators
        ]
    }


def _analysis_object(recipe: ResolvedRecipe) -> dict[str, Any]:
    assert recipe.analysis is not None
    return {
        "bootstrap_seed": recipe.analysis.bootstrap_seed,
        "bootstrap_resamples": recipe.analysis.bootstrap_resamples,
        "bootstrap_ci": recipe.analysis.bootstrap_ci,
        "paired_comparison": recipe.analysis.paired_comparison,
        "error_taxonomy": recipe.analysis.error_taxonomy,
    }


def generation_hash(recipe: ResolvedRecipe) -> str:
    """Identity of the applied generation inputs (no paths/roots)."""
    return tagged_digest("generation", _generation_object(recipe), domain=RECIPE_DOMAIN)


def evaluation_hash(recipe: ResolvedRecipe) -> str:
    """Identity of the resolved evaluator list in order."""
    return tagged_digest("evaluation", _evaluation_object(recipe), domain=RECIPE_DOMAIN)


def analysis_hash(recipe: ResolvedRecipe) -> str:
    """Identity of the applied analysis options (not a validity claim)."""
    return tagged_digest("analysis", _analysis_object(recipe), domain=RECIPE_DOMAIN)


def settings_hash(generation_digest: str, evaluation_digest: str, analysis_digest: str) -> str:
    """Identity binding the three settings sections."""
    return tagged_digest(
        "settings",
        {
            "generation_hash": generation_digest,
            "evaluation_hash": evaluation_digest,
            "analysis_hash": analysis_digest,
        },
        domain=RECIPE_DOMAIN,
    )


def execution_hash(inputs_digest: str, selection_digest: str, settings_digest: str) -> str:
    """Identity binding input identities with the applied settings."""
    return tagged_digest(
        "execution",
        {
            "inputs_hash": inputs_digest,
            "selection_hash": selection_digest,
            "settings_hash": settings_digest,
        },
        domain=RECIPE_DOMAIN,
    )


def build_execution_recipe(
    recipe: ResolvedRecipe, *, inputs_hash: str, selection_hash: str
) -> dict[str, Any]:
    """Assemble the ``execution-recipe.json`` object (no file re-reads).

    The input identities come from the same in-memory identity object built for
    this run. ``locations``/``metadata`` travel openly and never enter a hash.
    """
    assert recipe.analysis is not None
    assert recipe.locations is not None
    assert recipe.code_env is not None
    generation_digest = generation_hash(recipe)
    evaluation_digest = evaluation_hash(recipe)
    analysis_digest = analysis_hash(recipe)
    settings_digest = settings_hash(generation_digest, evaluation_digest, analysis_digest)
    return {
        "schema_version": RECIPE_SCHEMA_VERSION,
        "generation": _generation_object(recipe),
        "generation_hash": generation_digest,
        "evaluation": _evaluation_object(recipe),
        "evaluation_hash": evaluation_digest,
        "analysis": _analysis_object(recipe),
        "analysis_hash": analysis_digest,
        "settings_hash": settings_digest,
        "inputs_hash": inputs_hash,
        "selection_hash": selection_hash,
        "execution_hash": execution_hash(inputs_hash, selection_hash, settings_digest),
        "locations": {
            "suite_config_path": recipe.locations.suite_config_path,
            "corpus_root": recipe.locations.corpus_root,
        },
        "metadata": {
            "head": recipe.code_env.head,
            "dirty": recipe.code_env.dirty,
            "python_implementation": recipe.code_env.python_implementation,
            "python_version": recipe.code_env.python_version,
            "sloplab_version": recipe.code_env.sloplab_version,
            "uv_lock_sha256": recipe.code_env.uv_lock_sha256,
        },
    }


def write_execution_recipe(out_dir: Path, document: dict[str, Any]) -> Path:
    """Write ``execution-recipe.json`` for a successful study run."""
    path = out_dir / RECIPE_FILE_NAME
    path.write_bytes(canonical_json_bytes(document) + b"\n")
    return path
