"""Optional Jev typed evaluator package. Importing this module performs NO network calls.

``jev-typed`` is not in the default registry; see
:mod:`sloplab.evaluators.jev.evaluator` for explicit construction.
"""

from sloplab.evaluators.jev.evaluator import CONFIDENCE_SEMANTICS, JevEvaluator
from sloplab.evaluators.jev.failures import (
    FAILURE_CODES,
    BudgetExceeded,
    JevConfigError,
    JevEvaluationFailure,
)
from sloplab.evaluators.jev.mapping import (
    DECISION_CRITERIA,
    DIMENSION_ANCHORS,
    LabelMap,
    build_request,
    validate_model_id,
)
from sloplab.evaluators.jev.transport import (
    DEFAULT_API_KEY_ENV,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL_ID,
    TYPESAFE_NATIVE_BASE_URL,
    CountingTransport,
    HttpJevTransport,
    JevResponse,
    JevTransport,
)

__all__ = [
    "CONFIDENCE_SEMANTICS",
    "DECISION_CRITERIA",
    "DEFAULT_API_KEY_ENV",
    "DIMENSION_ANCHORS",
    "FAILURE_CODES",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_MODEL_ID",
    "TYPESAFE_NATIVE_BASE_URL",
    "BudgetExceeded",
    "CountingTransport",
    "HttpJevTransport",
    "JevConfigError",
    "JevEvaluationFailure",
    "JevEvaluator",
    "JevResponse",
    "JevTransport",
    "LabelMap",
    "build_request",
    "validate_model_id",
]
