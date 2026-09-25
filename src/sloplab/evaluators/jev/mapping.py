"""SlopLab <-> Jev typed request/response mapping (A-004).

One request carries the whole observation: a single three-option ``choice``
question for the triage decision and one ``score`` question per quality
dimension (1 choice + 5 scores = 6 questions per physical request). ``state`` is
the report text and nothing else.

Decision criteria derivation (``experiments/prompts/triage-v1.md``)
-------------------------------------------------------------------

The three ``criteria`` descriptions are the triage-v1 decision definitions
copied word for word. The only transformation is mechanical: the leading
``- "<option>": `` bullet marker is dropped and the source line wrap (newline
plus indentation) is joined with a single space.

=====================  ==========================================================
Decision               ``criteria`` text (verbatim from triage-v1.md)
=====================  ==========================================================
accept                 the report demonstrates a real, reproducible violation of
                       an explicit security boundary with calibrated impact.
reject                 no security boundary is crossed (intended behavior,
                       hardening suggestion, self-only impact, or claims
                       contradicted by their own evidence).
needs_manual_review    the report is plausible but unresolved - ambiguous
                       behavior, deployment-dependent impact, or missing
                       decisive evidence.
=====================  ==========================================================

The choice ``instructions`` adapt triage-v1's routing sentence ("Read the report
below and decide how a careful human triager should route it.") to the typed
layout, where the report is the ``state``; it is *not* verbatim. Every score
question ends with :data:`SCORE_GUIDANCE`, triage-v1's scoring sentence minus
the "each quality dimension from 0.0 to 1.0" range clause (levels replace it).

Dimension anchors
-----------------

:data:`DIMENSION_ANCHORS` is a provisional, versioned table
(:data:`DIMENSION_ANCHORS_VERSION`). It is **not** the A-002 rubric and carries
no accepted construct: it exists so the typed request is complete and
reproducible (R1-501). Replace it (and bump the version) when an accepted rubric
exists; results under different anchor versions must never be pooled.

Label binding (R1-509)
----------------------

:class:`LabelMap` binds the option keys Jev sees to SlopLab decisions. The
description attached to a decision is byte-identical under every map; only the
keys change. A label map changes names, never order; option order is a
separate stimulus controlled by ``option_order`` in :func:`build_request`
(default: canonical decision order accept, reject, needs_manual_review).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
import string
from dataclasses import dataclass
from typing import Any

from sloplab.evaluators.jev.failures import (
    RESPONSE_BAD_DISTRIBUTION,
    RESPONSE_MALFORMED,
    RESPONSE_MISSING_ANSWER,
    RESPONSE_MISSING_VERSION,
    RESPONSE_UNKNOWN_OPTION,
    JevResponseError,
)
from sloplab.models.enums import (
    CLAIM_EVIDENCE_CONSISTENCY,
    DIMENSIONS,
    EVIDENCE_COMPLETENESS,
    IMPACT_CALIBRATION,
    REPRODUCIBILITY,
    SCOPE_CONSISTENCY,
    Decision,
)

#: Version of this request/response mapping; recorded in result metadata.
MAPPING_VERSION = "jev-mapping-v1"

#: Where the decision criteria are derived from (repository-relative).
CRITERIA_SOURCE = "experiments/prompts/triage-v1.md"

DECISION_QUESTION_ID = "decision"
DIMENSION_QUESTION_PREFIX = "dim_"

#: Canonical option order; every label map emits options in this order.
DECISION_ORDER: tuple[Decision, ...] = (
    Decision.ACCEPT,
    Decision.REJECT,
    Decision.NEEDS_MANUAL_REVIEW,
)

DECISION_INSTRUCTIONS = "Decide how a careful human triager should route this vulnerability report."

#: Verbatim triage-v1 decision definitions (see the module derivation table).
DECISION_CRITERIA: dict[Decision, str] = {
    Decision.ACCEPT: (
        "the report demonstrates a real, reproducible violation of an explicit "
        "security boundary with calibrated impact."
    ),
    Decision.REJECT: (
        "no security boundary is crossed (intended behavior, hardening suggestion, "
        "self-only impact, or claims contradicted by their own evidence)."
    ),
    Decision.NEEDS_MANUAL_REVIEW: (
        "the report is plausible but unresolved - ambiguous behavior, "
        "deployment-dependent impact, or missing decisive evidence."
    ),
}


@dataclass(frozen=True)
class DecisionCriteria:
    """A versioned set of decision descriptions sent as the choice ``criteria``.

    ``version`` is recorded in result metadata; results under different criteria
    versions must never be pooled. The default, :data:`TRIAGE_V1`, is the verbatim
    triage-v1 set; other sets are experimental and live outside this module.
    """

    version: str
    texts: dict[Decision, str]

    def __post_init__(self) -> None:
        if not self.version or self.version != self.version.strip():
            raise ValueError("criteria version must be a non-empty string without padding")
        if set(self.texts) != set(DECISION_ORDER):
            raise ValueError("criteria must describe each decision exactly once")
        if any(not isinstance(t, str) or not t.strip() for t in self.texts.values()):
            raise ValueError("criteria texts must be non-empty strings")

    @property
    def sha256(self) -> str:
        """Hash of the ordered texts, for provenance."""
        payload = json.dumps([[d.value, self.texts[d]] for d in DECISION_ORDER])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


#: The default criteria set (verbatim triage-v1).
TRIAGE_V1 = DecisionCriteria(version="triage-v1", texts=DECISION_CRITERIA)

SCORE_GUIDANCE = (
    "Score based strictly on what the text contains; do not reward confident tone "
    "without substance, and do not penalize plain language when substance is present."
)

#: Provisional anchor table version (NOT the A-002 rubric).
DIMENSION_ANCHORS_VERSION = "jev-dim-anchors-v0-provisional"


@dataclass(frozen=True)
class DimensionSpec:
    """One score question: the dimension question and its ordered levels.

    ``anchors[0]`` is the lowest level; Jev numbers levels by array position.
    """

    question: str
    anchors: tuple[str, ...]

    @property
    def levels(self) -> int:
        return len(self.anchors)

    @property
    def instructions(self) -> str:
        return f"{self.question} {SCORE_GUIDANCE}"


#: Provisional three-level anchors per dimension (lowest first). Not A-002.
DIMENSION_ANCHORS: dict[str, DimensionSpec] = {
    REPRODUCIBILITY: DimensionSpec(
        question="How reproducible is the reported issue from what the report itself contains?",
        anchors=(
            "No actionable reproduction information: the steps, inputs, or environment "
            "needed to trigger the issue are absent.",
            "Partial reproduction information: some steps or inputs are given, but a "
            "reader could not reliably trigger the issue from the text alone.",
            "Complete reproduction information: concrete steps, inputs, and environment "
            "are given, so a reader could trigger the issue from the text alone.",
        ),
    ),
    EVIDENCE_COMPLETENESS: DimensionSpec(
        question="How complete is the evidence the report provides for its central claim?",
        anchors=(
            "Decisive evidence is missing: the claim is asserted without observed "
            "results, output, or other supporting material.",
            "Some supporting evidence is present, but evidence needed to confirm the "
            "claim is missing.",
            "The evidence needed to confirm the claim is present in the report.",
        ),
    ),
    CLAIM_EVIDENCE_CONSISTENCY: DimensionSpec(
        question="How consistent are the report's claims with its own evidence?",
        anchors=(
            "The report's own evidence contradicts or does not support its claims.",
            "The evidence partly supports the claims; some claims go beyond or "
            "conflict with what is shown.",
            "Every claim is supported by, and consistent with, the evidence shown.",
        ),
    ),
    IMPACT_CALIBRATION: DimensionSpec(
        question="How well is the stated impact calibrated to what the evidence shows?",
        anchors=(
            "The stated impact is missing or clearly overstated relative to what the "
            "evidence shows.",
            "The stated impact is partly supported; its severity or reach is somewhat "
            "overstated or understated.",
            "The stated impact matches what the evidence shows.",
        ),
    ),
    SCOPE_CONSISTENCY: DimensionSpec(
        question=(
            "How consistent is the report's scope (affected component, versions, "
            "preconditions, and security boundary) with its claims?"
        ),
        anchors=(
            "The scope is missing or inconsistent: the component, versions, "
            "preconditions, or boundary contradict the claims.",
            "The scope is partly stated or only partly consistent with the claims.",
            "The component, versions, preconditions, and security boundary are stated "
            "and consistent with the claims.",
        ),
    ),
}

#: Tolerance for a probability distribution summing to one.
DISTRIBUTION_TOLERANCE = 1e-6

_TOKEN_ALPHABET = string.ascii_lowercase
_TOKEN_LENGTH = 6


def dimension_question_id(dimension: str) -> str:
    return f"{DIMENSION_QUESTION_PREFIX}{dimension}"


def validate_model_id(model_id: str) -> str:
    """Return ``model_id`` if it names a pinned model, else raise ``ValueError``.

    Floating aliases are rejected (R1-506): any id containing ``latest`` (any
    case) and any ``~``-prefixed alias such as ``~typesafe/jev-latest``.
    """
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model_id must be a non-empty string")
    if model_id != model_id.strip():
        raise ValueError("model_id must not carry surrounding whitespace")
    if "latest" in model_id.lower():
        raise ValueError(f"floating model id {model_id!r} rejected; pin a version")
    if model_id.startswith("~"):
        raise ValueError(f"floating model alias {model_id!r} rejected; pin a version")
    return model_id


@dataclass(frozen=True)
class LabelMap:
    """Bijective binding of Jev option keys to SlopLab decisions.

    ``bindings`` is ordered by :data:`DECISION_ORDER` (one ``(key, decision)``
    pair per decision). ``kind`` is ``identity``, ``permutation``, or
    ``tokens``; ``seed`` records the generator seed (``None`` for identity).
    """

    kind: str
    bindings: tuple[tuple[str, Decision], ...]
    seed: int | None = None

    def __post_init__(self) -> None:
        keys = [key for key, _ in self.bindings]
        decisions = [decision for _, decision in self.bindings]
        if tuple(decisions) != DECISION_ORDER:
            raise ValueError("label map must bind each decision once, in canonical order")
        if any(not isinstance(key, str) or not key or key != key.strip() for key in keys):
            raise ValueError("label map keys must be non-empty strings without padding")
        if len(set(keys)) != len(keys):
            raise ValueError("label map keys must be unique")

    @classmethod
    def identity(cls) -> LabelMap:
        return cls(kind="identity", bindings=tuple((d.value, d) for d in DECISION_ORDER))

    @classmethod
    def permuted(cls, seed: int) -> LabelMap:
        """Seeded non-identity permutation of the three decision names.

        The key ``accept`` may then carry the *reject* description, etc.; the
        descriptions themselves never change.
        """
        names = [d.value for d in DECISION_ORDER]
        candidates = [p for p in itertools.permutations(names) if list(p) != names]
        chosen = random.Random(seed).choice(candidates)
        return cls(
            kind="permutation",
            bindings=tuple(zip(chosen, DECISION_ORDER, strict=True)),
            seed=seed,
        )

    @classmethod
    def random_tokens(cls, seed: int) -> LabelMap:
        """Seeded neutral lowercase tokens that differ from every decision name."""
        rng = random.Random(seed)
        reserved = {d.value for d in DECISION_ORDER}
        tokens: list[str] = []
        while len(tokens) < len(DECISION_ORDER):
            token = "".join(rng.choice(_TOKEN_ALPHABET) for _ in range(_TOKEN_LENGTH))
            if token not in reserved and token not in tokens:
                tokens.append(token)
        return cls(
            kind="tokens",
            bindings=tuple(zip(tokens, DECISION_ORDER, strict=True)),
            seed=seed,
        )

    @property
    def id(self) -> str:
        """Stable identifier: ``identity`` or ``<kind>:seed=<n>:<sha12>``."""
        if self.kind == "identity" and self == LabelMap.identity():
            return "identity"
        digest = hashlib.sha256(
            json.dumps([[k, d.value] for k, d in self.bindings]).encode("utf-8")
        ).hexdigest()[:12]
        return f"{self.kind}:seed={self.seed}:{digest}"

    def option_for(self, decision: Decision) -> str:
        for key, bound in self.bindings:
            if bound is decision:
                return key
        raise KeyError(decision)  # pragma: no cover - __post_init__ guarantees coverage

    def resolve(self, option: str) -> Decision:
        """Map a returned option key back to its decision (``KeyError`` if unknown)."""
        for key, decision in self.bindings:
            if key == option:
                return decision
        raise KeyError(option)

    def keys(self) -> tuple[str, ...]:
        return tuple(key for key, _ in self.bindings)

    def as_dict(self) -> dict[str, str]:
        return {key: decision.value for key, decision in self.bindings}


def validate_option_order(option_order: tuple[Decision, ...]) -> tuple[Decision, ...]:
    """Return ``option_order`` if it lists every decision exactly once."""
    if sorted(option_order, key=DECISION_ORDER.index) != list(DECISION_ORDER) or len(
        option_order
    ) != len(DECISION_ORDER):
        raise ValueError("option_order must list each decision exactly once")
    return tuple(option_order)


def build_request(
    report_text: str,
    *,
    model_id: str,
    label_map: LabelMap,
    option_order: tuple[Decision, ...] = DECISION_ORDER,
    criteria: DecisionCriteria = TRIAGE_V1,
) -> dict[str, Any]:
    """Render the typed ``/v1/systemone`` request body for one report.

    ``state`` is exactly ``report_text``. Question order: the decision choice,
    then the five dimension scores in :data:`DIMENSIONS` order. Decision options
    are emitted in ``option_order``; each option keeps its bound description,
    taken from ``criteria`` (default :data:`TRIAGE_V1`).
    """
    validate_model_id(model_id)
    validate_option_order(option_order)
    if not isinstance(report_text, str):
        raise TypeError("report_text must be a string")
    questions: dict[str, Any] = {
        DECISION_QUESTION_ID: {
            "type": "choice",
            "instructions": DECISION_INSTRUCTIONS,
            "criteria": {
                label_map.option_for(decision): criteria.texts[decision]
                for decision in option_order
            },
        }
    }
    for dimension in DIMENSIONS:
        spec = DIMENSION_ANCHORS[dimension]
        questions[dimension_question_id(dimension)] = {
            "type": "score",
            "instructions": spec.instructions,
            "criteria": list(spec.anchors),
        }
    return {"model": model_id, "state": report_text, "questions": questions}


def encode_request(body: dict[str, Any]) -> bytes:
    """The exact wire bytes for ``body`` (insertion order kept, compact, UTF-8).

    Key order is preserved on purpose: option order is part of the stimulus.
    ``request_sha256`` is the SHA-256 of these bytes.
    """
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )


@dataclass(frozen=True)
class DecodedResponse:
    """A response fully resolved into SlopLab terms.

    ``dimension_values`` are normalized to [0, 1] with
    ``value = score / (levels - 1)``: a mechanical linear rescale of Jev's
    expected level index, not an interval-quality validity claim.
    """

    model_version: str
    selected_option: str
    decision: Decision
    selected_probability: float
    jev_confidence: float | None
    decision_probabilities: dict[str, float]  # keyed by Decision value
    dimension_scores: dict[str, float]  # raw Jev score (expected level index)
    dimension_values: dict[str, float]  # normalized to [0, 1]
    dimension_probabilities: dict[str, dict[str, float]]
    usage: dict[str, float | None]


def _number(value: object) -> float | None:
    """``value`` as a finite float, or ``None`` (bools and non-finite values excluded)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _check_distribution(raw: object, expected_keys: tuple[str, ...]) -> dict[str, float]:
    """Validate a probability map; unknown keys and bad sums are distinct codes."""
    if not isinstance(raw, dict):
        raise JevResponseError(RESPONSE_BAD_DISTRIBUTION)
    if any(key not in expected_keys for key in raw):
        raise JevResponseError(RESPONSE_UNKNOWN_OPTION)
    if set(raw) != set(expected_keys):
        raise JevResponseError(RESPONSE_BAD_DISTRIBUTION)
    values: dict[str, float] = {}
    for key in expected_keys:
        value = _number(raw[key])
        if value is None or not 0.0 <= value <= 1.0:
            raise JevResponseError(RESPONSE_BAD_DISTRIBUTION)
        values[key] = value
    if abs(math.fsum(values.values()) - 1.0) > DISTRIBUTION_TOLERANCE:
        raise JevResponseError(RESPONSE_BAD_DISTRIBUTION)
    return values


def _typed_answer(answers: dict[str, Any], question_id: str, answer_type: str) -> dict[str, Any]:
    answer = answers.get(question_id)
    if not isinstance(answer, dict) or answer.get("type") != answer_type:
        raise JevResponseError(RESPONSE_MISSING_ANSWER)
    return answer


def _usage(body: dict[str, Any]) -> dict[str, float | None]:
    raw = body.get("usage")
    usage: dict[str, float | None] = {"input_tokens": None, "output_tokens": None, "cost": None}
    if isinstance(raw, dict):
        for key in usage:
            usage[key] = _number(raw.get(key))
    return usage


def decode_response(body: object, label_map: LabelMap) -> DecodedResponse:
    """Resolve a parsed response body, or raise :class:`JevResponseError`.

    Check order (first failing check wins): body shape -> version -> answers
    present -> decision choice/probabilities -> each dimension score. No
    default decision, probability, or dimension is ever substituted.
    """
    if not isinstance(body, dict):
        raise JevResponseError(RESPONSE_MALFORMED)
    version = body.get("model")
    if not isinstance(version, str) or not version.strip():
        raise JevResponseError(RESPONSE_MISSING_VERSION)
    answers = body.get("answers")
    if not isinstance(answers, dict):
        raise JevResponseError(RESPONSE_MISSING_ANSWER)

    decision_answer = _typed_answer(answers, DECISION_QUESTION_ID, "choice")
    selected = decision_answer.get("choice")
    if not isinstance(selected, str):
        raise JevResponseError(RESPONSE_MISSING_ANSWER)
    try:
        decision = label_map.resolve(selected)
    except KeyError:
        raise JevResponseError(RESPONSE_UNKNOWN_OPTION) from None
    option_probabilities = _check_distribution(
        decision_answer.get("probabilities"), label_map.keys()
    )
    jev_confidence_raw = decision_answer.get("confidence")
    jev_confidence: float | None = None
    if jev_confidence_raw is not None:
        jev_confidence = _number(jev_confidence_raw)
        if jev_confidence is None or not 0.0 <= jev_confidence <= 1.0:
            raise JevResponseError(RESPONSE_BAD_DISTRIBUTION)

    scores: dict[str, float] = {}
    values: dict[str, float] = {}
    dim_probabilities: dict[str, dict[str, float]] = {}
    for dimension in DIMENSIONS:
        spec = DIMENSION_ANCHORS[dimension]
        answer = _typed_answer(answers, dimension_question_id(dimension), "score")
        score = _number(answer.get("score"))
        if score is None:
            raise JevResponseError(RESPONSE_MISSING_ANSWER)
        top = spec.levels - 1
        if not 0.0 <= score <= top:
            raise JevResponseError(RESPONSE_BAD_DISTRIBUTION)
        level_keys = tuple(str(level) for level in range(spec.levels))
        dim_probabilities[dimension] = _check_distribution(answer.get("probabilities"), level_keys)
        scores[dimension] = score
        values[dimension] = score / top

    return DecodedResponse(
        model_version=version,
        selected_option=selected,
        decision=decision,
        selected_probability=option_probabilities[selected],
        jev_confidence=jev_confidence,
        decision_probabilities={
            label_map.resolve(key).value: p for key, p in option_probabilities.items()
        },
        dimension_scores=scores,
        dimension_values=values,
        dimension_probabilities=dim_probabilities,
        usage=_usage(body),
    )
