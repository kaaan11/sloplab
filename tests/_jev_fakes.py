"""Offline fakes shared by the Jev typed-evaluator tests. Nothing here touches the network."""

from __future__ import annotations

import socket
from collections.abc import Callable
from typing import Any

import pytest

from sloplab.corpus.parser import parse_report
from sloplab.evaluators.jev.mapping import (
    DECISION_QUESTION_ID,
    DIMENSION_ANCHORS,
    LabelMap,
    dimension_question_id,
)
from sloplab.evaluators.jev.transport import JevResponse
from sloplab.models.enums import DIMENSIONS, Decision
from sloplab.models.evaluation import EvaluationContext

REPORT_TEXT = "# T\n\n## Summary\n\nA complete report body for Jev adapter testing.\n"
CASE_ID = "canonical-jev-001"


class NetworkBlocked(AssertionError):
    """Raised by the socket guard; deliberately not an ``OSError`` so no layer swallows it."""


def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every socket creation, connect, and DNS lookup fail loudly."""

    def _refuse(*args: object, **kwargs: object) -> Any:
        raise NetworkBlocked("network access attempted in an offline test")

    monkeypatch.setattr(socket, "socket", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    monkeypatch.setattr(socket, "getaddrinfo", _refuse)


def make_report() -> Any:
    return parse_report(REPORT_TEXT, fixture_id=CASE_ID, path="x")


def make_context() -> EvaluationContext:
    return EvaluationContext(
        report=make_report(),
        case_id=CASE_ID,
        labels={"expected_decision": "reject"},  # must be ignored by the adapter
    )


def score_answer(score: float, probabilities: list[float]) -> dict[str, Any]:
    return {
        "type": "score",
        "score": score,
        "confidence": 0.5,
        "probabilities": {str(i): p for i, p in enumerate(probabilities)},
    }


def valid_body(
    label_map: LabelMap | None = None,
    *,
    selected: Decision = Decision.NEEDS_MANUAL_REVIEW,
    probabilities: dict[Decision, float] | None = None,
    jev_confidence: float = 0.4,
    model_version: str = "jev-1.13.0",
) -> dict[str, Any]:
    """A well-formed ``/v1/systemone`` response for the six requested questions."""
    label_map = label_map or LabelMap.identity()
    probabilities = probabilities or {
        Decision.ACCEPT: 0.2,
        Decision.REJECT: 0.1,
        Decision.NEEDS_MANUAL_REVIEW: 0.7,
    }
    answers: dict[str, Any] = {
        DECISION_QUESTION_ID: {
            "type": "choice",
            "choice": label_map.option_for(selected),
            "confidence": jev_confidence,
            "probabilities": {label_map.option_for(d): p for d, p in probabilities.items()},
        }
    }
    for index, dimension in enumerate(DIMENSIONS):
        assert DIMENSION_ANCHORS[dimension].levels == 3
        # Scores 0.5, 0.75, 1.0, 1.25, 1.5 -> normalized 0.25 ... 0.75.
        answers[dimension_question_id(dimension)] = score_answer(
            0.5 + 0.25 * index, [0.5 - 0.125 * index, 0.5, 0.125 * index]
        )
    return {
        "model": model_version,
        "answers": answers,
        "usage": {"input_tokens": 812, "output_tokens": 40, "cost": 0.0000341},
    }


Step = JevResponse | BaseException


class ScriptedTransport:
    """Inner transport double: plays back responses/exceptions, recording every body."""

    def __init__(self, *steps: Step, repeat_last: bool = False) -> None:
        self._steps = list(steps)
        self._repeat_last = repeat_last
        self.bodies: list[dict[str, Any]] = []

    @property
    def calls(self) -> int:
        return len(self.bodies)

    def decide(self, body: dict[str, Any]) -> JevResponse:
        self.bodies.append(body)
        if len(self._steps) > 1 or not self._repeat_last:
            step = self._steps.pop(0)
        else:
            step = self._steps[0]
        if isinstance(step, BaseException):
            raise step
        return step


def respond(body: Any) -> JevResponse:
    return JevResponse.from_json(body, latency_ms=3)


def recording_sleep() -> tuple[list[float], Callable[[float], None]]:
    waits: list[float] = []
    return waits, waits.append
