"""Presentation mutation operators.

These operators change how a report *reads* without changing what it *claims*:
professionalize_language upgrades tone and grammar while preserving every defect;
confidence_overstatement hardens certainty language. They measure whether evaluators
reward style over substance.
"""

from __future__ import annotations

import random
import re
from typing import Any

from sloplab.models.enums import (
    CLAIM_EVIDENCE_CONSISTENCY,
    IMPACT_CALIBRATION,
    MutationCategory,
)
from sloplab.models.report import ReportDocument
from sloplab.mutations.base import MutationSpec, register

_CONTRACTION_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("doesn't", "does not"),
    ("don't", "do not"),
    ("can't", "cannot"),
    ("won't", "will not"),
    ("isn't", "is not"),
    ("it's", "it is"),
    ("didn't", "did not"),
    ("shouldn't", "should not"),
)

_REGISTER_UPGRADES: tuple[tuple[str, str], ...] = (
    ("bug", "defect"),
    ("weird behavior", "anomalous behavior"),
    ("broken", "functionally incorrect"),
    ("a lot of", "considerable"),
    ("kind of", "somewhat"),
    ("stuff", "content"),
    ("things", "elements"),
    ("big deal", "significant concern"),
    ("totally", "entirely"),
    ("really", "materially"),
)

_POLITE_PREAMBLE: str = (
    "This report summarizes findings obtained exclusively through authorized testing "
    "of a sandboxed demo environment.\n\n"
)

_SENTENCE_END_RE = re.compile(r"([.!?])\s+(?=[a-z])")


class ProfessionalizeLanguage:
    spec = MutationSpec(
        name="professionalize_language",
        category=MutationCategory.PRESENTATION,
        description=(
            "Expands contractions, upgrades informal vocabulary to formal register, "
            "normalizes punctuation, and adds a neutral professional preamble - "
            "without altering any claim, evidence, or finding."
        ),
        dimension_deltas={},  # substance untouched by design
        presentation_strength="increased",
    )

    def apply(
        self,
        document: ReportDocument,
        rng: random.Random,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        _ = parameters
        text = document.raw_text

        applied: list[str] = []
        for old, new in _CONTRACTION_REPLACEMENTS:
            count = text.count(old)
            if count:
                text = text.replace(old, new)
                applied.append(f"contraction:{old}")

        for old, new in _REGISTER_UPGRADES:
            pattern = re.compile(r"\b" + re.escape(old) + r"\b", re.IGNORECASE)
            if pattern.search(text):
                # Preserve capitalization of the first letter where needed.
                text = pattern.sub(
                    lambda m: new if m.group(0).islower() else new.capitalize(), text
                )
                applied.append(f"register:{old}")

        text = text.replace("!", ".").replace("!!", ".")

        # Capitalize first letter after sentence ends (skip code fences).
        out_lines: list[str] = []
        in_fence = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                out_lines.append(line)
                continue
            if not in_fence and stripped and stripped[0].islower() and not stripped.startswith("#"):
                line = line.replace(stripped[0], stripped[0].upper(), 1)
            out_lines.append(line)
        text = "\n".join(out_lines)

        # Insert the polite preamble right after the H1 heading.
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("# "):
                lines.insert(index + 1, "")
                lines.insert(index + 2, _POLITE_PREAMBLE.rstrip())
                break
        text = "\n".join(lines)

        rng.getrandbits(1)  # deterministic stream even though this op is fully rule-based
        return text, {"transformations": applied}


class ConfidenceOverstatement:
    spec = MutationSpec(
        name="confidence_overstatement",
        category=MutationCategory.PRESENTATION,
        description=(
            "Hardens certainty language ('may', 'possibly', 'appears') into absolute "
            "assertions without adding supporting evidence."
        ),
        dimension_deltas={
            IMPACT_CALIBRATION: -0.2,
            CLAIM_EVIDENCE_CONSISTENCY: -0.25,
        },
    )

    _HEDGES: tuple[tuple[str, str], ...] = (
        ("may allow", "allows"),
        ("might allow", "allows"),
        ("could potentially allow", "allows"),
        ("could allow", "allows"),
        ("possibly", "certainly"),
        ("potentially", "definitively"),
        ("appears to", "does"),
        ("suggesting that", "proving that"),
        ("likely", "certainly"),
        ("unclear whether", "confirmed that"),
    )

    def apply(
        self,
        document: ReportDocument,
        rng: random.Random,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        _ = parameters
        text = document.raw_text
        applied: list[str] = []
        for old, new in self._HEDGES:
            if old in text.lower():
                idx = text.lower().find(old)
                text = text[:idx] + new + text[idx + len(old) :]
                applied.append(f"{old}->{new}")
        rng.getrandbits(1)
        return text, {"certainty_upgrades": applied}


_ = CLAIM_EVIDENCE_CONSISTENCY  # reserved for future consistency-aware presentation ops

register(ProfessionalizeLanguage())
register(ConfidenceOverstatement())
