"""Dalga B (#49): study-v02 lock — committed records + current code == committed analysis.

The committed ``records.jsonl`` plus the current metric definitions (via the
same builder the ``sloplab study`` publisher uses) must reproduce the
committed ``analysis.json`` field by field: floats with
``math.isclose(rel_tol=1e-9)``, decisions/counts/strings exactly. A hand edit
of any single field fails the test (proven by
``test_comparator_catches_single_leaf_difference``).
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

import pytest

from sloplab.reporting.analysis import ANALYSIS_DEFINITION_VERSION
from sloplab.reporting.study_analysis import build_study_analysis
from sloplab.reporting.writers import read_run_jsonl

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_DIR = REPO_ROOT / "experiments" / "results" / "deterministic" / "study-v02"

# Frozen study options from experiments/configs/deterministic-study-v0.2.yaml
# (schema defaults: resamples=2000, ci=0.95) and the resolved recipe
# (bootstrap_seed = base_seed = 20260825; manifest.json records the seed).
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_CI = 0.95
BOOTSTRAP_SEED = 20260825

EXPECTED_CASE_ROWS = 594

REL_TOL = 1e-9

# Provenance keys are new by design (contract #49 item 3): asserted
# separately, excluded from the field-by-field document comparison.
PROVENANCE_KEYS = ("metric_definition_version", "python_version")


def _recomputed_analysis() -> dict[str, Any]:
    _, records = read_run_jsonl(STUDY_DIR / "records.jsonl")
    assert len(records) == EXPECTED_CASE_ROWS, f"expected {EXPECTED_CASE_ROWS} rows"
    return build_study_analysis(
        records,
        bootstrap_resamples=BOOTSTRAP_RESAMPLES,
        bootstrap_ci=BOOTSTRAP_CI,
        bootstrap_seed=BOOTSTRAP_SEED,
    )


def _assert_match(path: str, committed: Any, recomputed: Any) -> None:
    """Field-by-field comparison: exact for bool/str/None, isclose for numbers."""
    if isinstance(committed, bool) or isinstance(recomputed, bool):
        assert committed is recomputed, f"{path}: {committed!r} != {recomputed!r}"
        return
    if isinstance(committed, (int, float)) and isinstance(recomputed, (int, float)):
        assert math.isclose(float(recomputed), float(committed), rel_tol=REL_TOL), (
            f"{path}: {committed!r} != {recomputed!r}"
        )
        return
    if isinstance(committed, str) or isinstance(recomputed, str):
        assert committed == recomputed, f"{path}: {committed!r} != {recomputed!r}"
        return
    if committed is None or recomputed is None:
        assert committed is recomputed, f"{path}: {committed!r} != {recomputed!r}"
        return
    if isinstance(committed, dict) and isinstance(recomputed, dict):
        assert set(committed) == set(recomputed), (
            f"{path}: keys {sorted(set(committed) ^ set(recomputed))} differ"
        )
        for key in sorted(committed):
            _assert_match(f"{path}.{key}", committed[key], recomputed[key])
        return
    if isinstance(committed, list) and isinstance(recomputed, list):
        assert len(committed) == len(recomputed), (
            f"{path}: lengths {len(committed)} != {len(recomputed)}"
        )
        for index, (old, new) in enumerate(zip(committed, recomputed, strict=True)):
            _assert_match(f"{path}[{index}]", old, new)
        return
    raise AssertionError(f"{path}: type mismatch {type(committed)} vs {type(recomputed)}")


def test_committed_analysis_matches_recomputation() -> None:
    """Lock: committed records + current code reproduce the committed analysis."""
    committed = json.loads((STUDY_DIR / "analysis.json").read_text(encoding="utf-8"))
    recomputed = _recomputed_analysis()
    assert committed.get("metric_definition_version") == ANALYSIS_DEFINITION_VERSION
    assert recomputed["metric_definition_version"] == ANALYSIS_DEFINITION_VERSION
    for document in (committed, recomputed):
        assert isinstance(document.get("python_version"), str)
        assert document["python_version"]
    rest_committed = {k: v for k, v in committed.items() if k not in PROVENANCE_KEYS}
    rest_recomputed = {k: v for k, v in recomputed.items() if k not in PROVENANCE_KEYS}
    _assert_match("analysis", rest_committed, rest_recomputed)


def test_comparator_catches_single_leaf_difference() -> None:
    """The lock cannot be fooled by a hand edit of any single field."""
    base: dict[str, Any] = {
        "count": 3,
        "flag": True,
        "name": "rules-baseline",
        "score": 0.8114478114478114,
        "missing": None,
        "nested": {"series": [1.0, 2.0], "label": "x"},
    }
    _assert_match("root", base, copy.deepcopy(base))
    # Within-tolerance float noise passes; anything else must raise.
    noisy = copy.deepcopy(base)
    noisy["score"] += 1e-12
    _assert_match("root", base, noisy)

    mutations = ["count", "flag", "name", "score", "missing", "nested.series", "nested.label"]
    for field in mutations:
        tampered = copy.deepcopy(base)
        if field == "count":
            tampered["count"] += 1
        elif field == "flag":
            tampered["flag"] = False
        elif field == "name":
            tampered["name"] += "!"
        elif field == "score":
            tampered["score"] += 0.001
        elif field == "missing":
            tampered["missing"] = 0
        elif field == "nested.series":
            tampered["nested"]["series"][0] += 0.001
        else:
            tampered["nested"]["label"] += "!"
        with pytest.raises(AssertionError):
            _assert_match("root", base, tampered)
    dropped = copy.deepcopy(base)
    del dropped["nested"]
    with pytest.raises(AssertionError):
        _assert_match("root", base, dropped)
