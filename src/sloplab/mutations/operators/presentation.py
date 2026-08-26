"""Presentation mutation operators.

These operators change how a report *reads* without changing what it *claims*:
professionalize_language upgrades tone and grammar while preserving every defect;
confidence_overstatement hardens certainty language. They measure whether evaluators
reward style over substance.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from functools import partial
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


def split_code_fences(text: str) -> list[tuple[bool, str]]:
    """Split ``text`` into ``(is_fenced, chunk)`` segments preserving order.

    A fenced segment starts at a line beginning with ``` (after stripping) and
    ends at the matching closing-fence line; the fence delimiter lines themselves
    belong to the fenced chunk so they are never rewritten.
    """
    chunks: list[tuple[bool, str]] = []
    current: list[str] = []
    current_fenced = False
    in_fence = False

    def flush() -> None:
        if current:
            chunks.append((current_fenced, "\n".join(current)))

    for line in text.splitlines():
        if line.strip().startswith("```"):
            if not in_fence:
                flush()
                current, current_fenced = [line], True
                in_fence = True
            else:
                current.append(line)
                flush()
                current, current_fenced = [], False
                in_fence = False
        else:
            if not in_fence and current_fenced:
                # already flushed above; start a fresh unfenced chunk
                pass
            current.append(line)
    flush()
    return chunks


def _match_case(match: re.Match[str], replacement: str) -> str:
    """Preserve capitalization of the first letter where needed."""
    return replacement if match.group(0).islower() else replacement.capitalize()


def _rewrite_unfenced(text: str, transform: Callable[[str], str]) -> str:
    """Apply ``transform`` to every unfenced chunk and reassemble the text."""
    parts: list[str] = []
    for is_fenced, chunk in split_code_fences(text):
        parts.append(chunk if is_fenced else transform(chunk))
    return "\n".join(parts)


class ProfessionalizeLanguage:
    spec = MutationSpec(
        name="professionalize_language",
        category=MutationCategory.PRESENTATION,
        description=(
            "Expands contractions, upgrades informal vocabulary to formal register, "
            "normalizes punctuation, and adds a neutral professional preamble - "
            "without altering any claim, evidence, finding, or fenced code block."
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

        def _apply_contractions_and_register(chunk: str) -> str:
            for old, new in _CONTRACTION_REPLACEMENTS:
                count = chunk.count(old)
                if count:
                    chunk = chunk.replace(old, new)
                    if f"contraction:{old}" not in applied:
                        applied.append(f"contraction:{old}")
            for old, new in _REGISTER_UPGRADES:
                pattern = re.compile(r"\b" + re.escape(old) + r"\b", re.IGNORECASE)
                if pattern.search(chunk):
                    chunk = pattern.sub(partial(_match_case, replacement=new), chunk)
                    if f"register:{old}" not in applied:
                        applied.append(f"register:{old}")
            return chunk.replace("!", ".").replace("!!", ".")

        text = _rewrite_unfenced(text, _apply_contractions_and_register)

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

        # Insert the polite preamble right after the H1 heading (never inside a fence).
        lines = text.splitlines()
        in_fence = False
        for index, line in enumerate(lines):
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if not in_fence and line.startswith("# "):
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
        # Each hedge pattern replaces at most its first occurrence, scanning
        # unfenced prose in reading order; fenced code is never rewritten.
        for old, new in self._HEDGES:
            pattern = re.compile(re.escape(old), re.IGNORECASE)
            chunks = split_code_fences(text)
            replaced = False
            rebuilt: list[str] = []
            for _index, (is_fenced, chunk) in enumerate(chunks):
                if not replaced and not is_fenced and pattern.search(chunk):
                    rebuilt.append(pattern.sub(new, chunk, count=1))
                    replaced = True
                    applied.append(f"{old}->{new}")
                else:
                    rebuilt.append(chunk)
            if replaced:
                text = "\n".join(rebuilt)

        rng.getrandbits(1)
        if not applied:
            # Machine-readable no-op signal (R01): the materializer skips derived
            # cases whose operator left the report text unchanged.
            return text, {"note": "no hedged language found outside code fences"}
        return text, {"certainty_upgrades": applied}


_ = CLAIM_EVIDENCE_CONSISTENCY  # reserved for future consistency-aware presentation ops

register(ProfessionalizeLanguage())
register(ConfidenceOverstatement())
