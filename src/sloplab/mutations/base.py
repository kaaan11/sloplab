"""Mutation operator base types, registry, and deterministic seed derivation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Protocol

from sloplab.models.enums import (
    Decision,
    MutationCategory,
    ReportClass,
    canonical_expected_decision,
)
from sloplab.models.report import ReportDocument


@dataclass(frozen=True)
class MutationSpec:
    """Declarative metadata and scoring expectations for one mutation operator.

    ``dimension_deltas`` are applied to the parent fixture's expected dimensions
    (clamped to [0, 1]) to produce the derived case's expected dimensions.
    ``decision_by_parent_class`` defines the expected triage decision of a derived
    case given the parent's ground-truth class; the default keeps the parent's own
    expected decision (mutations usually do not change what *should* happen, they
    degrade report quality).
    """

    name: str
    category: MutationCategory
    description: str
    dimension_deltas: dict[str, float] = field(default_factory=dict)
    decision_by_parent_class: dict[ReportClass, Decision] = field(default_factory=dict)
    claim_quality: str = "unchanged"
    presentation_strength: str = "unchanged"

    def expected_decision(self, parent_class: ReportClass) -> Decision:
        if parent_class in self.decision_by_parent_class:
            return self.decision_by_parent_class[parent_class]
        return canonical_expected_decision(parent_class)


class MutationOperator(Protocol):
    """A deterministic text-level mutation over a parsed report document."""

    spec: MutationSpec

    def apply(
        self,
        document: ReportDocument,
        rng: Any,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Return ``(mutated_markdown_text, recorded_parameters)``."""
        ...  # pragma: no cover


_REGISTRY: dict[str, MutationOperator] = {}


def register(operator: MutationOperator) -> None:
    _REGISTRY[operator.spec.name] = operator


def get_operator(name: str) -> MutationOperator:
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "<none registered>"
        raise KeyError(f"unknown mutation operator '{name}'; registered: {known}") from None


def list_operators() -> list[str]:
    return sorted(_REGISTRY)


def derive_seed(base_seed: int, parent_id: str, operator_name: str, variant_index: int) -> int:
    """Deterministic 64-bit seed from stable inputs (D-0008)."""
    payload = f"{base_seed}|{parent_id}|{operator_name}|{variant_index}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def apply_dimension_deltas(
    parent_dimensions: dict[str, float], deltas: dict[str, float]
) -> dict[str, float]:
    out = dict(parent_dimensions)
    for dim, delta in deltas.items():
        base = out.get(dim, 0.5)
        out[dim] = round(min(1.0, max(0.0, base + delta)), 3)
    return out


# Import operator modules so their registrations run.
from sloplab.mutations.operators import evidence, impact, presentation, technical  # noqa: E402

_ = (evidence, impact, presentation, technical)  # registration side effects


__all__ = [
    "MutationOperator",
    "MutationSpec",
    "apply_dimension_deltas",
    "derive_seed",
    "get_operator",
    "list_operators",
    "register",
]
