"""E4b: operator-metric eligibility is complete and honestly labeled."""

from __future__ import annotations

from sloplab.mutations.base import get_operator, list_operators
from sloplab.reporting.analysis import operator_metric_eligibility
from sloplab.scoring.metrics import PRESENTATION_OPERATORS


def test_eligibility_covers_every_registered_operator() -> None:
    """No operator silently falls out of the measurement table."""
    table = operator_metric_eligibility()
    assert set(table) == set(list_operators())
    for name, row in table.items():
        assert row["category"] == str(get_operator(name).spec.category)
        assert row["degrading_capable"] == bool(get_operator(name).spec.decision_by_parent_class)
        assert row["presentation"] == (name in PRESENTATION_OPERATORS)
        assert row["detection_eligible"] == row["degrading_capable"]
        assert row["susceptibility_eligible"] == row["presentation"]
        assert "quality" in row["invariance"] or "robustness" in row["invariance"]


def test_presentation_set_matches_categories() -> None:
    """Susceptibility eligibility equals the presentation category share."""
    table = operator_metric_eligibility()
    assert {n for n, r in table.items() if r["presentation"]} == {
        "professionalize_language",
        "confidence_overstatement",
    }
    assert table["professionalize_language"]["degrading_capable"] is False
    assert table["impact_inflation"]["degrading_capable"] is True
    assert table["impact_inflation"]["susceptibility_eligible"] is False
