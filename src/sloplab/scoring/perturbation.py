"""Semantic perturbation distance and robustness budget curve computation (Phase 8)."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from sloplab.models.run import CaseRecord
from sloplab.scoring.metrics import decision_correct

_WORD_RE = re.compile(r"\b\w+\b")


def _term_frequency_vector(text: str) -> Counter[str]:
    words = [w.lower() for w in _WORD_RE.findall(text)]
    return Counter(words)


def compute_cosine_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity between word vectors of two texts."""
    vec_a = _term_frequency_vector(text_a)
    vec_b = _term_frequency_vector(text_b)

    if not vec_a or not vec_b:
        return 1.0 if not vec_a and not vec_b else 0.0

    intersection = set(vec_a) & set(vec_b)
    dot_product = sum(vec_a[w] * vec_b[w] for w in intersection)

    norm_a = math.sqrt(sum(c * c for c in vec_a.values()))
    norm_b = math.sqrt(sum(c * c for c in vec_b.values()))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return min(1.0, max(0.0, dot_product / (norm_a * norm_b)))


def compute_text_perturbation(original_text: str, mutated_text: str) -> float:
    """Calculate normalized perturbation distance [0, 1].

    0.0 represents zero modification; higher values denote greater structural/semantic drift.
    """
    similarity = compute_cosine_similarity(original_text, mutated_text)
    return round(1.0 - similarity, 4)


def compute_robustness_perturbation_curve(
    records: list[CaseRecord],
    bins: int = 5,
) -> list[dict[str, Any]]:
    """Compute evaluator decision accuracy across perturbation budget intervals.

    Each bin represents a perturbation slice (e.g. 0.0 - 0.2, 0.2 - 0.4).
    """
    eligible = [
        r
        for r in records
        if r.expected_decision is not None and "perturbation_distance" in r.evaluation_metadata
    ]
    if not eligible:
        return []

    bin_width = 1.0 / bins
    curve: list[dict[str, Any]] = []

    for b in range(bins):
        lo = b * bin_width
        hi = (b + 1) * bin_width
        if b == bins - 1:
            members = [
                r
                for r in eligible
                if lo <= float(r.evaluation_metadata["perturbation_distance"]) <= hi
            ]
        else:
            members = [
                r
                for r in eligible
                if lo <= float(r.evaluation_metadata["perturbation_distance"]) < hi
            ]

        accuracy = (
            sum(1 for r in members if decision_correct(r)) / len(members) if members else None
        )
        curve.append(
            {
                "bin": b,
                "range": [round(lo, 2), round(hi, 2)],
                "count": len(members),
                "accuracy": round(accuracy, 4) if accuracy is not None else None,
            }
        )

    return curve
