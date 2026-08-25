"""Experiment configuration schemas for SlopLab studies."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from sloplab.models.manifest import StrictModel


class SuiteRef(StrictModel):
    """Where the benchmark suite definition and its corpus live."""

    config_path: str = Field(min_length=1)
    corpus_root: str = Field(min_length=1)


class EvaluatorSpec(StrictModel):
    """One evaluator participating in the study."""

    name: str = Field(min_length=1)
    config: dict[str, str] = Field(default_factory=dict)


class AnalysisOptions(StrictModel):
    bootstrap_resamples: int = Field(default=2000, ge=100)
    bootstrap_ci: float = Field(default=0.95, gt=0.0, lt=1.0)
    paired_comparison: bool = True
    error_taxonomy: bool = True


class ProvenanceOptions(StrictModel):
    record_commit_sha: bool = True
    record_suite_hash: bool = True
    record_evaluator_config_hash: bool = True


class DeterministicStudyConfig(StrictModel):
    schema_version: Literal[2] = 2
    name: str = Field(min_length=1)
    description: str = ""
    suite: SuiteRef
    base_seed: int = Field(ge=0)
    repeat_index: int = Field(default=0, ge=0)
    evaluators: list[EvaluatorSpec] = Field(min_length=1)
    analysis: AnalysisOptions = AnalysisOptions()
    provenance: ProvenanceOptions = ProvenanceOptions()

    @field_validator("evaluators")
    @classmethod
    def _unique_names(cls, value: list[EvaluatorSpec]) -> list[EvaluatorSpec]:
        names = [e.name for e in value]
        if len(set(names)) != len(names):
            raise ValueError(f"evaluator names must be unique: {names}")
        return value


class LLMBudget(StrictModel):
    max_requests: int = Field(gt=0)
    request_timeout_s: int = Field(default=60, gt=0)
    max_retries_per_case: int = Field(default=2, ge=0)
    min_interval_ms: int = Field(default=0, ge=0)


class LLMPilotConfig(StrictModel):
    schema_version: Literal[2] = 2
    name: str = Field(min_length=1)
    description: str = ""
    suite: SuiteRef
    base_seed: int = Field(ge=0)
    repeats: int = Field(default=3, ge=1)
    model_env: str = Field(min_length=1)
    endpoint_env: str = Field(min_length=1)
    api_key_env: str = Field(min_length=1)
    prompt_file: str = Field(min_length=1)
    budget: LLMBudget
    case_selection: Literal["canonical_first"] = "canonical_first"
    max_cases: int | None = None

    @field_validator("case_selection")
    @classmethod
    def _known_selection(cls, value: str) -> str:
        if value != "canonical_first":
            raise ValueError(f"unsupported case_selection {value!r}")
        return value
