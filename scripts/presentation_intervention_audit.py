"""Deterministic four-arm audit of style and authorization-cue interventions.

Uses the rules baseline on standalone canonical reports only. Existing authored
plain/polished pairs are analyzed separately by presentation_pair_audit.py.
The historical composite arm is checked against style followed by cue insertion.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from sloplab.corpus.loader import load_canonical_fixture
from sloplab.corpus.parser import parse_report
from sloplab.evaluators.rules.baseline import RulesBaselineEvaluator
from sloplab.models.enums import Decision
from sloplab.models.evaluation import EvaluationContext
from sloplab.mutations.operators.presentation import (
    AddAuthorizationPreamble,
    ProfessionalizeLanguage,
    ProfessionalizeStyle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    evaluator = RulesBaselineEvaluator()
    totals: Counter[str] = Counter()
    accepted: Counter[str] = Counter()
    changed: Counter[str] = Counter()
    text_changed: Counter[str] = Counter()
    arms = ("original", "style", "cue", "composite")
    for path in sorted((REPO_ROOT / "corpus/canonical").glob("*/manifest.yaml")):
        fixture = load_canonical_fixture(path.parent, REPO_ROOT / "corpus")
        if fixture.manifest.pair_id is not None:
            continue
        original = fixture.report.raw_text
        style, _ = ProfessionalizeStyle().apply(fixture.report, random.Random(0))
        cue, _ = AddAuthorizationPreamble().apply(fixture.report, random.Random(0))
        composite, _ = ProfessionalizeLanguage().apply(fixture.report, random.Random(0))
        styled_doc = parse_report(style, fixture_id=fixture.fixture_id, path="style")
        recomposed, _ = AddAuthorizationPreamble().apply(styled_doc, random.Random(0))
        if composite.rstrip("\n") != recomposed.rstrip("\n"):
            raise AssertionError(f"historical composite differs for {fixture.fixture_id}")
        texts = dict(zip(arms, (original, style, cue, composite), strict=True))
        decisions: dict[str, Decision] = {}
        for arm, text in texts.items():
            report = parse_report(text, fixture_id=fixture.fixture_id, path=arm)
            context = EvaluationContext(report=report, case_id=fixture.fixture_id)
            decision = evaluator.evaluate(report, context).decision
            decisions[arm] = decision
            totals[arm] += 1
            accepted[arm] += int(decision == Decision.ACCEPT)
            text_changed[arm] += int(text != original)
        for arm in arms[1:]:
            changed[arm] += int(decisions[arm] != decisions["original"])
    print(
        json.dumps(
            {
                "population": "44 standalone canonical reports; authored pairs excluded",
                "total": dict(totals),
                "accepted": dict(accepted),
                "text_changed": dict(text_changed),
                "decision_changed_from_original": dict(changed),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
