"""Mutation planning: deterministic assignment of operators to canonical fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sloplab.corpus.loader import CanonicalFixture
from sloplab.models.enums import Decision
from sloplab.models.manifest import ExpectedEffect
from sloplab.models.suite import ClassPolicy, SuiteConfig
from sloplab.mutations.base import (
    MutationSpec,
    apply_dimension_deltas,
    derive_seed,
    get_operator,
)


@dataclass(frozen=True)
class PlannedMutation:
    parent: CanonicalFixture
    operator_name: str
    spec: MutationSpec
    variant_index: int
    seed: int
    base_seed: int
    case_id: str
    expected_decision: Decision
    expected_dimensions: dict[str, float]
    expected_effect: ExpectedEffect

    @property
    def parent_id(self) -> str:
        return self.parent.fixture_id


def _case_id(parent_id: str, operator_name: str, variant_index: int) -> str:
    short = parent_id.removeprefix("canonical-")
    op_slug = operator_name.replace("_", "-")
    return f"mut-{short}-{op_slug}-{variant_index + 1:02d}"


def _rotation_offset(fixture_index: int, policy: ClassPolicy) -> int:
    # Spread operator coverage across the corpus: fixture i starts at position i.
    return fixture_index % len(policy.operators)


def plan_fixture(
    fixture: CanonicalFixture,
    policy: ClassPolicy,
    *,
    fixture_index: int,
    base_seed: int,
) -> list[PlannedMutation]:
    """Plan ``variants_per_fixture`` mutations for one fixture."""
    plans: list[PlannedMutation] = []
    offset = _rotation_offset(fixture_index, policy)
    for variant_index in range(policy.variants_per_fixture):
        operator_name = policy.operators[(offset + variant_index) % len(policy.operators)]
        spec = get_operator(operator_name).spec
        seed = derive_seed(base_seed, fixture.fixture_id, operator_name, variant_index)
        plans.append(
            PlannedMutation(
                parent=fixture,
                operator_name=operator_name,
                spec=spec,
                variant_index=variant_index,
                seed=seed,
                base_seed=base_seed,
                case_id=_case_id(fixture.fixture_id, operator_name, variant_index),
                expected_decision=spec.expected_decision(fixture.manifest.report_class),
                expected_dimensions=apply_dimension_deltas(
                    fixture.manifest.ground_truth.expected_dimensions, spec.dimension_deltas
                ),
                expected_effect=ExpectedEffect(
                    report_validity="unchanged",
                    claim_quality=cast(Any, spec.claim_quality),
                    presentation_strength=cast(Any, spec.presentation_strength),
                ),
            )
        )
    return plans


def plan_suite(
    config: SuiteConfig, fixtures: list[CanonicalFixture]
) -> tuple[list[PlannedMutation], dict[str, int]]:
    """Plan all mutations for a suite. Returns plans plus per-group fixture counts."""
    all_plans: list[PlannedMutation] = []
    counters: dict[str, int] = {}
    group_counts: dict[str, int] = {}

    for index, fixture in enumerate(fixtures):
        key, policy = config.policy_for_fixture(
            fixture.manifest.report_class, fixture.manifest.pair_id
        )
        group_counts[key] = group_counts.get(key, 0) + 1
        plans = plan_fixture(
            fixture,
            policy,
            fixture_index=counters.get(key, 0),
            base_seed=config.base_seed,
        )
        counters[key] = counters.get(key, 0) + 1
        _ = index
        all_plans.extend(plans)

    return all_plans, group_counts
