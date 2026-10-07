"""Benchmark suite configuration schema."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from sloplab.models.enums import PRESENTATION_PAIR_KEY, SUITE_POLICY_KEYS, ReportClass
from sloplab.models.manifest import StrictModel


class ClassPolicy(StrictModel):
    """How many mutation variants to derive per fixture of one report class."""

    variants_per_fixture: int = Field(ge=0)
    operators: list[str] = Field(min_length=1)

    @field_validator("operators")
    @classmethod
    def _unique_operators(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError(f"operator list must not contain duplicates: {value}")
        return value


SuitePolicyKey = Literal["valid", "invalid", "review", "presentation_pair"]


class SuiteConfig(StrictModel):
    """Declarative definition of a reproducible benchmark suite.

    Policies apply per fixture group: ``valid`` / ``invalid`` / ``review`` target
    fixtures by report class; ``presentation_pair`` targets fixtures that carry a
    ``pair_id`` (their mutations test presentation robustness).
    """

    schema_version: int = 1
    name: str = Field(min_length=1)
    description: str = ""
    base_seed: int = Field(ge=0)
    corpus_root: str = "corpus/canonical"
    include_canonical_cases: bool = True
    policies: dict[SuitePolicyKey, ClassPolicy]

    @field_validator("policies")
    @classmethod
    def _nonempty_policies(
        cls, value: dict[SuitePolicyKey, ClassPolicy]
    ) -> dict[SuitePolicyKey, ClassPolicy]:
        if not value:
            raise ValueError(
                f"suite must define at least one class policy; known keys: {SUITE_POLICY_KEYS}"
            )
        return value

    def policy_for_fixture(
        self, report_class: ReportClass, pair_id: str | None
    ) -> tuple[str, ClassPolicy]:
        """Resolve the applicable policy key and policy for a canonical fixture."""
        if pair_id is not None and PRESENTATION_PAIR_KEY in self.policies:
            return PRESENTATION_PAIR_KEY, self.policies[PRESENTATION_PAIR_KEY]
        key = report_class.value
        if key in self.policies:
            return key, self.policies[key]
        raise KeyError(f"no suite policy covers report class '{key}'")

    def estimated_case_count(self, canonical_count_by_group: dict[str, int]) -> dict[str, int]:
        """Estimated derived-case counts per policy group, given fixture counts."""
        out: dict[str, int] = {}
        for group, count in canonical_count_by_group.items():
            if group in self.policies:
                out[group] = count * self.policies[group].variants_per_fixture
        return out
