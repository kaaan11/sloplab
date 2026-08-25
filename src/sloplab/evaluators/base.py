"""Evaluator protocol, registry, and helpers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sloplab.models.evaluation import EvaluationContext, EvaluationResult
from sloplab.models.report import ReportDocument


@runtime_checkable
class Evaluator(Protocol):
    """The normalized evaluator contract (docs/evaluator-contract.md).

    Implementations receive the parsed report plus a harness-supplied context and
    must return an :class:`EvaluationResult`. Evaluators must be deterministic given
    their configuration; stochastic evaluators own their seeding internally.
    """

    name: str
    version: str

    def evaluate(
        self,
        report: ReportDocument,
        context: EvaluationContext,
    ) -> EvaluationResult: ...


_EVALUATOR_REGISTRY: dict[str, Evaluator] = {}


def register_evaluator(evaluator: Evaluator) -> None:
    _EVALUATOR_REGISTRY[evaluator.name] = evaluator


def get_evaluator(name: str) -> Evaluator:
    try:
        return _EVALUATOR_REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_EVALUATOR_REGISTRY)) or "<none registered>"
        raise KeyError(f"unknown evaluator '{name}'; registered: {known}") from None


def list_evaluators() -> list[str]:
    return sorted(_EVALUATOR_REGISTRY)


from sloplab.evaluators.oracle import OracleEvaluator
from sloplab.evaluators.rules.baseline import RulesBaselineEvaluator
from sloplab.evaluators.rules.evidence_graph import EvidenceGraphBaselineEvaluator

register_evaluator(OracleEvaluator())
register_evaluator(RulesBaselineEvaluator())
register_evaluator(EvidenceGraphBaselineEvaluator())

__all__ = [
    "Evaluator",
    "get_evaluator",
    "list_evaluators",
    "register_evaluator",
]
