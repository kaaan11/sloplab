"""Evaluator protocol, registry, oracle, and rules baseline."""

from sloplab.evaluators.base import Evaluator, get_evaluator, list_evaluators, register_evaluator
from sloplab.evaluators.oracle import OracleEvaluator
from sloplab.evaluators.rules.baseline import RulesBaselineEvaluator

__all__ = [
    "Evaluator",
    "OracleEvaluator",
    "RulesBaselineEvaluator",
    "get_evaluator",
    "list_evaluators",
    "register_evaluator",
]
