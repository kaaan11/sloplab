"""Mutation engine: operators, specs, registry, and deterministic seeding."""

from sloplab.mutations.base import (
    MutationSpec,
    apply_dimension_deltas,
    derive_seed,
    get_operator,
    list_operators,
)
from sloplab.mutations.textops import first_matching_section, remove_section, replace_section_body

__all__ = [
    "MutationSpec",
    "apply_dimension_deltas",
    "derive_seed",
    "first_matching_section",
    "get_operator",
    "list_operators",
    "remove_section",
    "replace_section_body",
]
