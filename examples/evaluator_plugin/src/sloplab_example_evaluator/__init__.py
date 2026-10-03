"""A packaging example with a constant action, not a trained triage evaluator."""

from sloplab.models.enums import DIMENSIONS, Decision
from sloplab.models.evaluation import DimensionScores, EvaluationContext, EvaluationResult
from sloplab.models.report import ReportDocument


class ConstantReviewEvaluator:
    name = "example-review-plugin"
    version = "0.1.0"
    requires_labels = False

    def evaluate(self, report: ReportDocument, context: EvaluationContext) -> EvaluationResult:
        return EvaluationResult(
            case_id=context.case_id,
            evaluator_name=self.name,
            evaluator_version=self.version,
            decision=Decision.NEEDS_MANUAL_REVIEW,
            confidence=0.5,
            dimensions=DimensionScores.from_dict(dict.fromkeys(DIMENSIONS, 0.5)),
        )


def make() -> ConstantReviewEvaluator:
    return ConstantReviewEvaluator()
