"""Performance regression tests for conditional-boundary matching (review finding 1).

The tempered ``no boundary <clause> crossed`` patterns must stay fast on
adversarial repetitive near-miss input (reports are untrusted input). The
pattern-level tests exercise the match iterator the evaluator itself uses;
the evaluate-level tests cover the whole ``evaluate()`` path. Bounds are
generous on purpose: the pre-fix code takes multiple seconds here, the fixed
code takes well under a tenth of a second.
"""

from __future__ import annotations

import time

from sloplab.corpus.parser import parse_report
from sloplab.evaluators.base import get_evaluator
from sloplab.evaluators.rules import baseline as rules_baseline
from sloplab.models.evaluation import EvaluationContext

_NEAR_MISS_UNIT = "no boundary "

_SCAFFOLD = """\
# Missing authorization in DemoVault module

## Summary

The lookup endpoint returns another tenant's object when requested directly.

## Affected Component

DemoVault object lookup endpoint at https://demo.example.org.

## Affected Versions

DemoVault 2.3.0 through 2.4.1 (demo builds only).

## Preconditions

Valid low-privilege account on the demo instance.

## Reproduction Steps

1. Sign in as user A (tenant 1).
2. Send `GET /objects/42` with tenant 2 context.
3. Observe the response body.

## Observed Result

The object of tenant 2 is returned without an authorization check.

## Expected Security Boundary

BOUNDARY_SENTENCE

## Impact

Medium confidentiality impact on demo data only.
"""


def _near_miss(chars: int) -> str:
    return (_NEAR_MISS_UNIT * ((chars // len(_NEAR_MISS_UNIT)) + 1))[:chars]


def _evaluate_boundary(boundary: str) -> object:
    doc = parse_report(
        _SCAFFOLD.replace("BOUNDARY_SENTENCE", boundary), fixture_id="perf", path="x"
    )
    evaluator = get_evaluator("rules-baseline")
    return evaluator.evaluate(doc, EvaluationContext(report=doc, case_id="perf", labels={}))


def test_match_iterator_40k_near_miss() -> None:
    text = _near_miss(40_000)
    started = time.perf_counter()
    list(rules_baseline._iter_no_boundary_matches(text))
    assert time.perf_counter() - started < 0.5


def test_match_iterator_80k_near_miss() -> None:
    text = _near_miss(80_000)
    started = time.perf_counter()
    list(rules_baseline._iter_no_boundary_matches(text))
    assert time.perf_counter() - started < 0.5


def test_match_iterator_80k_between_near_miss() -> None:
    text = ("no boundary between things " * 3000)[:80_000]
    started = time.perf_counter()
    list(rules_baseline._iter_no_boundary_matches(text))
    assert time.perf_counter() - started < 0.5


def test_full_evaluate_40k_near_miss() -> None:
    started = time.perf_counter()
    _evaluate_boundary(_near_miss(40_000))
    assert time.perf_counter() - started < 1.0


def test_full_evaluate_80k_near_miss() -> None:
    started = time.perf_counter()
    _evaluate_boundary(_near_miss(80_000))
    assert time.perf_counter() - started < 1.0
