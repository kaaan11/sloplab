"""Benchmark suite configuration schema."""

from __future__ import annotations

from pydantic import Field, field_validator

from sloplab.models.enums import ReportClass
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


class SuiteConfig(StrictModel):
    """Declarative definition of a reproducible benchmark suite."""

    schema_version: int = 1
    name: str = Field(min_length=1)
    description: str = ""
    base_seed: int = Field(ge=0)
    corpus_root: str = "corpus/canonical"
    include_canonical_cases: bool = True
    policies: dict[ReportClass, ClassPolicy]

    @field_validator("policies")
    @classmethod
    def _nonempty_policies(
        cls, value: dict[ReportClass, ClassPolicy]
    ) -> dict[ReportClass, ClassPolicy]:
        if not value:
            raise ValueError("suite must define at least one class policy")
        return value

    def estimated_case_count(self, canonical_count_by_class: dict[str, int]) -> dict[str, int]:
        """Estimated derived-case counts per class, given canonical fixture counts."""
        out: dict[str, int] = {}
        for report_class, policy in self.policies.items():
            n = canonical_count_by_class.get(report_class.value, 0)
            out[report_class.value] = n * policy.variants_per_fixture
        return out
