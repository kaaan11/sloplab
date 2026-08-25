"""Tests for the evaluator protocol and the oracle evaluator."""

from __future__ import annotations

import pytest

from sloplab.corpus.parser import parse_report
from sloplab.evaluators.base import get_evaluator, list_evaluators
from sloplab.models.enums import Decision
from sloplab.models.evaluation import EvaluationContext, EvaluationResult


def make_context(case_id: str = "canonical-t-001", **labels: object) -> EvaluationContext:
    report = parse_report("# T\n\n## Summary\n\nBody.\n", fixture_id=case_id, path="x")
    return EvaluationContext(report=report, case_id=case_id, labels=dict(labels))


class TestRegistry:
    def test_builtins_registered(self) -> None:
        names = list_evaluators()
        assert "oracle" in names
        assert "rules-baseline" in names

    def test_unknown_evaluator_lists_known(self) -> None:
        with pytest.raises(KeyError, match="registered:"):
            get_evaluator("nope")


class TestProtocolConformance:
    def test_builtin_evaluators_satisfy_protocol(self) -> None:
        from sloplab.evaluators.base import Evaluator

        for name in ("oracle", "rules-baseline"):
            evaluator = get_evaluator(name)
            assert isinstance(evaluator, Evaluator)


class TestOracle:
    def test_echoes_expected_decision_and_dims(self) -> None:
        oracle = get_evaluator("oracle")
        result = oracle.evaluate(
            make_context().report,
            make_context(
                expected_decision="needs_manual_review",
                expected_dimensions={"reproducibility": 0.2},
            ),
        )
        assert isinstance(result, EvaluationResult)
        assert result.decision == Decision.NEEDS_MANUAL_REVIEW
        assert result.confidence == 1.0
        assert result.dimensions.reproducibility == 0.2
        assert result.dimensions.scope_consistency == 0.5  # default fill

    def test_requires_expected_decision_label(self) -> None:
        oracle = get_evaluator("oracle")
        ctx = make_context()
        with pytest.raises(ValueError, match="expected_decision"):
            oracle.evaluate(ctx.report, make_context())

    def test_rejects_bad_decision_values(self) -> None:
        oracle = get_evaluator("oracle")
        ctx = make_context(expected_decision="banana")
        with pytest.raises(ValueError):
            oracle.evaluate(ctx.report, ctx)
