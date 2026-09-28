"""Presentation mutation operators.

The historical professionalize_language operator combines register edits with an
authorization preamble. New operators isolate those two interventions so a style
effect is not confused with an asserted provenance cue.
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

# Hyphen policy (issue #26, binding contract 2026-09-27): hyphenated compound
# words are preserved, so the lookarounds reject [\w-] neighbors exactly. The
# pattern is assembled from ``NOT = "!"`` because a literal ``(?<!`` written
# inline was mangled by the publishing pipeline (the '!' after '?' or '<' was
# stripped); building it programmatically keeps the compiled pattern correct.
# Exported as ``HEDGE`` so the contract test can pin it.
NOT = "!"  # ASCII 33
HEDGE = re.compile(r"(?<" + NOT + r"[\w-])likely(?" + NOT + r"[\w-])", re.IGNORECASE)


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


def _professionalize_style(text: str) -> tuple[str, list[str]]:
    """Apply only the historical register and punctuation edits."""
    applied: list[str] = []

    def transform(chunk: str) -> str:
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
        return re.sub(r"!+", ".", chunk)

    text = _rewrite_unfenced(text, transform)
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
    return "\n".join(out_lines), applied


def _add_authorization_preamble(text: str) -> str:
    """Insert the historical cue after the first H1, outside fenced code."""
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
    return "\n".join(lines)


class ProfessionalizeLanguage:
    spec = MutationSpec(
        name="professionalize_language",
        category=MutationCategory.PRESENTATION,
        description=(
            "Expands contractions, upgrades informal vocabulary to formal register, "
            "normalizes punctuation, and adds an authorization preamble. This is "
            "a historical composite operator; do not attribute its effect to style alone."
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
        text, applied = _professionalize_style(document.raw_text)
        text = _add_authorization_preamble(text)

        rng.getrandbits(1)  # deterministic stream even though this op is fully rule-based
        return text, {"transformations": applied}


class ProfessionalizeStyle:
    spec = MutationSpec(
        name="professionalize_style",
        category=MutationCategory.PRESENTATION,
        description="Changes register and punctuation without inserting a provenance claim.",
        dimension_deltas={},
        presentation_strength="increased",
    )

    def apply(
        self,
        document: ReportDocument,
        rng: random.Random,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        _ = parameters
        text, applied = _professionalize_style(document.raw_text)
        if document.raw_text.endswith("\n"):
            text += "\n"
        rng.getrandbits(1)
        return text, {"transformations": applied}


class AddAuthorizationPreamble:
    spec = MutationSpec(
        name="add_authorization_preamble",
        category=MutationCategory.PROVENANCE,
        description="Adds an asserted authorized-testing cue without changing the report's style.",
        dimension_deltas={},
    )

    def apply(
        self,
        document: ReportDocument,
        rng: random.Random,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        _ = parameters
        text = _add_authorization_preamble(document.raw_text)
        if document.raw_text.endswith("\n"):
            text += "\n"
        rng.getrandbits(1)
        return text, {"added_authorization_preamble": text != document.raw_text}


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

    @staticmethod
    def _compile_hedge(phrase: str) -> re.Pattern[str]:
        """Hedge matcher with the contract's hyphen-aware lookarounds."""
        return re.compile(
            r"(?<" + NOT + r"[\w-])" + re.escape(phrase) + r"(?" + NOT + r"[\w-])", re.IGNORECASE
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
            pattern = self._compile_hedge(old)
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
register(ProfessionalizeStyle())
register(AddAuthorizationPreamble())
register(ConfidenceOverstatement())
