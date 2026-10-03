"""Evaluator protocol, registry and offline reference implementations."""

from sloplab.evaluators.base import Evaluator, get_evaluator, list_evaluators, register_evaluator
from sloplab.evaluators.oracle import OracleEvaluator
from sloplab.evaluators.rules.baseline import RulesBaselineEvaluator
from sloplab.evaluators.text_quality import TextQualityBaselineEvaluator

__all__ = [
    "Evaluator",
    "OracleEvaluator",
    "RulesBaselineEvaluator",
    "TextQualityBaselineEvaluator",
    "get_evaluator",
    "list_evaluators",
    "register_evaluator",
]
