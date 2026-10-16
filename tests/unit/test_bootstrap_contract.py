"""Direct library calls validate bootstrap parameters consistently."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from sloplab.scoring.comparison import bootstrap_accuracy_ci, cluster_bootstrap_accuracy_ci
from tests.unit.test_scoring import record


@pytest.mark.parametrize("bootstrap", [bootstrap_accuracy_ci, cluster_bootstrap_accuracy_ci])
@pytest.mark.parametrize("ci", [0.0, 1.0, -0.1, 1.2, float("nan"), float("inf")])
@pytest.mark.parametrize("empty", [False, True])
def test_invalid_confidence_rejected(bootstrap: Callable[..., Any], ci: float, empty: bool) -> None:
    with pytest.raises(ValueError, match="ci must be in"):
        bootstrap([] if empty else [record("case")], ci=ci, resamples=4)


@pytest.mark.parametrize("bootstrap", [bootstrap_accuracy_ci, cluster_bootstrap_accuracy_ci])
@pytest.mark.parametrize("resamples", [0, -1])
def test_invalid_resample_count_rejected(bootstrap: Callable[..., Any], resamples: int) -> None:
    with pytest.raises(ValueError, match="resamples must be >= 1"):
        bootstrap([record("case")], resamples=resamples)


@pytest.mark.parametrize("ci", [0.95, 1e-300, 1 - 1e-15])
def test_single_resample_extreme_confidence_is_bounded(ci: float) -> None:
    records = [record("case")]
    assert bootstrap_accuracy_ci(records, ci=ci, resamples=1) == (1.0, 1.0, 1.0)
    clustered = cluster_bootstrap_accuracy_ci(records, ci=ci, resamples=1)
    assert clustered.accuracy == {records[0].evaluator_name: (1.0, 1.0)}
