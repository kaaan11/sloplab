"""Minimal BYOE contract example, not a validated triage evaluator.

Fully offline and deterministic. It uses report structure alone and therefore
cannot establish whether a vulnerability is real. No registration or labels.
"""

from sloplab.models.enums import DIMENSIONS, Decision
from sloplab.models.evaluation import DimensionScores, EvaluationContext, EvaluationResult
from sloplab.models.report import ReportDocument


class MyEvaluator:
    name = "example-structure"
    version = "1.0.0"
    requires_labels = False

    def evaluate(self, report: ReportDocument, context: EvaluationContext) -> EvaluationResult:
        # Deliberately naive heuristic: teach the contract, not security competence.
        has_steps = bool(report.find_sections(r"reproduction\s+steps?|steps\s+to\s+reproduce"))
        score = 0.7 if has_steps else 0.2
        return EvaluationResult(
            evaluator_name=self.name,
            evaluator_version=self.version,
            case_id=context.case_id,
            decision=Decision.NEEDS_MANUAL_REVIEW if has_steps else Decision.REJECT,
            confidence=0.5,
            dimensions=DimensionScores.from_dict(dict.fromkeys(DIMENSIONS, score)),
            rationale="Structure-only teaching example; no technical validity claim.",
        )


def make() -> MyEvaluator:
    """Zero-argument factory selected by --evaluator-module examples/my_evaluator.py:make."""
    return MyEvaluator()
