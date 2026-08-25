"""Oracle evaluator: test-only ground-truth reader used to validate scoring plumbing.

The oracle is NOT a triage system. It echoes the expected decision carried in the
evaluation context's ``labels`` (populated by the harness from fixture manifests).
If an oracle-scored benchmark disagrees with expectations, the harness itself is
broken - which is exactly what this evaluator is for detecting.
"""

from __future__ import annotations

from typing import Any

from sloplab.models.enums import DIMENSIONS, Decision
from sloplab.models.evaluation import DimensionScores, EvaluationContext, EvaluationResult
from sloplab.models.report import ReportDocument


class OracleEvaluator:
    name = "oracle"
    version = "0.1.0"

    def evaluate(
        self,
        report: ReportDocument,
        context: EvaluationContext,
    ) -> EvaluationResult:
        expected = context.labels.get("expected_decision")
        if expected is None:
            raise ValueError(
                f"oracle evaluator requires labels['expected_decision'] for case "
                f"'{context.case_id}'"
            )
        decision = Decision(expected)

        dims_raw: Any = context.labels.get("expected_dimensions") or {}
        dims = {d: float(dims_raw.get(d, 0.5)) for d in DIMENSIONS}

        return EvaluationResult(
            evaluator_name=self.name,
            evaluator_version=self.version,
            case_id=context.case_id,
            decision=decision,
            confidence=1.0,
            dimensions=DimensionScores.from_dict(dims),
            findings=[],
            rationale="oracle: echoes harness-supplied ground truth",
            metadata={"source": "labels"},
        )
