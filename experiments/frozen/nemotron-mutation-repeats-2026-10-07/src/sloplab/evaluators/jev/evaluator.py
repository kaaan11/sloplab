"""Jev typed evaluator (``jev-typed``, A-004). Mock-only until A-006.

Not registered in the default evaluator registry: it needs an explicitly
capped transport, and the live transport needs an API key from the
environment. Live usage (NOT used by tests/CI)::

    from sloplab.evaluators.jev import CountingTransport, HttpJevTransport, JevEvaluator

    transport = CountingTransport(HttpJevTransport.openrouter(), max_requests=10)
    evaluator = JevEvaluator(transport=transport, model_id="typesafe/jev-1.13")

Result semantics:

- ``decision`` is the selected option resolved through the :class:`LabelMap`.
- ``confidence`` is the probability Jev assigns to the selected option
  (``confidence_semantics = "selected_class_probability"``, R1-505). Jev's own
  ``confidence`` (a spread summary, not P(correct)) goes to
  ``metadata["jev_confidence"]``.
- Dimensions: ``value = score / (levels - 1)`` where ``score`` is Jev's
  expected level index in ``[0, levels - 1]``; a mechanical linear rescale
  onto [0, 1] under the provisional anchor table, not a validated measure.
- ``findings`` stay empty and ``rationale`` stays ``""``: Jev produces no
  explanations, and none are invented (capabilities marked unsupported).

Any unresolvable response or transport outcome raises
:class:`JevEvaluationFailure` with a code from
:mod:`sloplab.evaluators.jev.failures`; no default decision is assigned.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from typing import Any

from sloplab import __version__
from sloplab.evaluators.jev.failures import (
    BUDGET_EXCEEDED,
    RESPONSE_MALFORMED,
    TRANSPORT_RATE_LIMITED,
    BudgetExceeded,
    JevConfigError,
    JevEvaluationFailure,
    JevRateLimited,
    JevResponseError,
    JevTimeout,
    JevTransportError,
    jev_failure,
)
from sloplab.evaluators.jev.mapping import (
    DECISION_ORDER,
    DIMENSION_ANCHORS,
    DIMENSION_ANCHORS_VERSION,
    MAPPING_VERSION,
    TRIAGE_V1,
    DecisionCriteria,
    DecodedResponse,
    LabelMap,
    build_request,
    decode_response,
    dimension_question_id,
    encode_request,
    validate_model_id,
    validate_option_order,
)
from sloplab.evaluators.jev.transport import OPENROUTER_MODEL_ID, CountingTransport, JevResponse
from sloplab.models.enums import DIMENSIONS, Decision
from sloplab.models.evaluation import DimensionScores, EvaluationContext, EvaluationResult
from sloplab.models.report import ReportDocument

CONFIDENCE_SEMANTICS = "selected_class_probability"


class JevEvaluator:
    """Typed Jev adapter implementing the standard evaluator protocol.

    ``transport`` must be a :class:`CountingTransport` so every physical
    request, retries included, is capped. Retries: timeouts and 429/529 are
    retried up to ``max_retries`` times; a ``Retry-After`` wait is honored in
    full or not at all (a wait above ``max_wait_s`` ends the evaluation as
    ``transport.rate_limited`` without sleeping). Without ``Retry-After`` the
    wait is ``backoff_s * 2 ** (attempt - 1)``. 401/422 and other permanent
    statuses are never retried.
    """

    name = "jev-typed"
    version = __version__
    # Content-based: evaluates report text only; never needs ground-truth labels.
    requires_labels = False

    def __init__(
        self,
        transport: CountingTransport,
        *,
        model_id: str = OPENROUTER_MODEL_ID,
        label_map: LabelMap | None = None,
        option_order: tuple[Decision, ...] = DECISION_ORDER,
        criteria: DecisionCriteria = TRIAGE_V1,
        max_retries: int = 1,
        backoff_s: float = 1.0,
        max_wait_s: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not isinstance(transport, CountingTransport):
            raise JevConfigError("JevEvaluator requires a CountingTransport (hard dispatch cap)")
        try:
            self._model_id = validate_model_id(model_id)
        except ValueError as exc:
            raise JevConfigError(str(exc)) from None
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
            raise JevConfigError("max_retries must be an integer >= 0")
        if backoff_s < 0 or max_wait_s < 0:
            raise JevConfigError("backoff_s and max_wait_s must be >= 0")
        if not isinstance(criteria, DecisionCriteria):
            raise JevConfigError("criteria must be a DecisionCriteria")
        self._criteria = criteria
        self._transport = transport
        self._label_map = label_map if label_map is not None else LabelMap.identity()
        try:
            self._option_order = validate_option_order(option_order)
        except ValueError as exc:
            raise JevConfigError(str(exc)) from None
        self._max_retries = max_retries
        self._backoff_s = float(backoff_s)
        self._max_wait_s = float(max_wait_s)
        self._sleep = sleep

    @property
    def label_map(self) -> LabelMap:
        return self._label_map

    @property
    def model_id(self) -> str:
        return self._model_id

    def evaluate(
        self,
        report: ReportDocument,
        context: EvaluationContext,
    ) -> EvaluationResult:
        """Return the normalized observation, or raise :class:`JevEvaluationFailure`."""
        _ = context.labels  # deliberately unused; the adapter is content-based
        body = build_request(
            report.raw_text,
            model_id=self._model_id,
            label_map=self._label_map,
            option_order=self._option_order,
            criteria=self._criteria,
        )
        request_sha256 = hashlib.sha256(encode_request(body)).hexdigest()

        response, attempts = self._dispatch(body, request_sha256)
        try:
            parsed_body = json.loads(response.raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise jev_failure(
                RESPONSE_MALFORMED, attempts=attempts, request_sha256=request_sha256
            ) from None
        try:
            decoded = decode_response(parsed_body, self._label_map)
        except JevResponseError as exc:
            raise jev_failure(exc.code, attempts=attempts, request_sha256=request_sha256) from None
        return self._to_result(
            decoded,
            case_id=context.case_id,
            request_sha256=request_sha256,
            response=response,
            attempts=attempts,
        )

    # --- dispatch --------------------------------------------------------

    def _dispatch(self, body: dict[str, Any], request_sha256: str) -> tuple[JevResponse, int]:
        attempt = 0
        while True:
            attempt += 1
            try:
                return self._transport.decide(body), attempt
            except BudgetExceeded:
                raise self._fail(BUDGET_EXCEEDED, attempt, request_sha256) from None
            except JevRateLimited as exc:
                if attempt > self._max_retries:
                    raise self._fail(exc.code, attempt, request_sha256, exc.status) from None
                wait = exc.retry_after_s
                if wait is None:
                    wait = self._backoff_s * 2 ** (attempt - 1)
                if wait > self._max_wait_s:
                    # Never shorten a provider wait: give up instead.
                    raise self._fail(
                        TRANSPORT_RATE_LIMITED, attempt, request_sha256, exc.status
                    ) from None
                self._sleep(wait)
            except JevTimeout as exc:
                if attempt > self._max_retries:
                    raise self._fail(exc.code, attempt, request_sha256, exc.status) from None
                self._sleep(self._backoff_s * 2 ** (attempt - 1))
            except JevTransportError as exc:
                # Permanent HTTP statuses (401/422/...) and status-less errors.
                raise self._fail(exc.code, attempt, request_sha256, exc.status) from None

    @staticmethod
    def _fail(
        code: str, attempts: int, request_sha256: str, status: int | None = None
    ) -> JevEvaluationFailure:
        return jev_failure(
            code, attempts=attempts, request_sha256=request_sha256, http_status=status
        )

    # --- result ----------------------------------------------------------

    def _to_result(
        self,
        decoded: DecodedResponse,
        *,
        case_id: str,
        request_sha256: str,
        response: JevResponse,
        attempts: int,
    ) -> EvaluationResult:
        probabilities: dict[str, dict[str, float]] = {"decision": decoded.decision_probabilities}
        for dimension in DIMENSIONS:
            probabilities[dimension_question_id(dimension)] = decoded.dimension_probabilities[
                dimension
            ]
        return EvaluationResult(
            evaluator_name=self.name,
            evaluator_version=self.version,
            case_id=case_id,
            decision=decoded.decision,
            confidence=decoded.selected_probability,
            dimensions=DimensionScores.from_dict(decoded.dimension_values),
            findings=[],
            rationale="",
            metadata={
                "adapter": "jev-typed",
                "failed": False,
                "mapping_version": MAPPING_VERSION,
                "dimension_anchors_version": DIMENSION_ANCHORS_VERSION,
                "dimension_levels": {d: DIMENSION_ANCHORS[d].levels for d in DIMENSIONS},
                "model_requested": self._model_id,
                "model_version": decoded.model_version,
                "confidence_semantics": CONFIDENCE_SEMANTICS,
                "jev_confidence": decoded.jev_confidence,
                "selected_option": decoded.selected_option,
                "probabilities": probabilities,
                "dimension_scores_raw": decoded.dimension_scores,
                "label_map_id": self._label_map.id,
                "label_map": self._label_map.as_dict(),
                "option_order": [decision.value for decision in self._option_order],
                "criteria_version": self._criteria.version,
                "criteria_sha256": self._criteria.sha256,
                "usage": decoded.usage,
                "request_questions": 1 + len(DIMENSIONS),
                "adapter_attempts": attempts,
                "request_sha256": request_sha256,
                "response_sha256": hashlib.sha256(response.raw).hexdigest(),
                "latency_ms": response.latency_ms,
                "capabilities": {"findings": "unsupported", "rationale": "unsupported"},
            },
        )
