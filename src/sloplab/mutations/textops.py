"""Line-span editing utilities for mutating parsed reports deterministically."""

from __future__ import annotations

import hashlib
import re

from sloplab.models.report import ReportDocument, ReportSection

_NUMBERED_STEP_RE = re.compile(r"^\s*\d+[.)]\s+")
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
# Mirrors parser.py fence syntax (single source of truth stays there; the
# equality is pinned by test so profile drift fails loudly, not silently).
_FENCE_RE = re.compile(r"^\s*(?P<fence>`{3,}|~{3,})")
_HEADING_LINE_RE = re.compile(r"^#{1,6}\s+")


class StaleSpanError(ValueError):
    """A splice was asked to apply a span not authorized for the document."""


def first_matching_section(document: ReportDocument, pattern: str) -> ReportSection | None:
    matches = document.find_sections(pattern)
    return matches[0] if matches else None


def replace_section_body(
    document: ReportDocument,
    section: ReportSection,
    new_body: str,
    *,
    expected_document_identity: str,
) -> str:
    """Render the document with one section's body replaced (heading preserved).

    ``new_body`` may be empty, which leaves only the heading. The source
    identity is mandatory (no default, not skippable): pass the identity
    captured with the span from its source document. Stale or foreign spans
    raise :class:`StaleSpanError` instead of splicing.
    """
    _require_authorized(document, section, expected_document_identity=expected_document_identity)
    lines = document.raw_text.splitlines()
    prefix = lines[: section.location.start_line]  # through the heading line
    replacement = new_body.splitlines() if new_body else []
    suffix = lines[section.location.end_line :]
    return "\n".join(prefix + replacement + suffix)


def remove_section(
    document: ReportDocument, section: ReportSection, *, expected_document_identity: str
) -> str:
    """Render the document with an entire section (heading and body) removed.

    The source identity is mandatory (no default, not skippable): pass the
    identity captured with the span from its source document. Stale or
    foreign spans raise :class:`StaleSpanError` instead of splicing.
    """
    _require_authorized(document, section, expected_document_identity=expected_document_identity)
    lines = document.raw_text.splitlines()
    start = section.location.start_line - 1
    end = section.location.end_line
    # Swallow one adjacent blank line to avoid doubled blanks after removal.
    if (
        end < len(lines)
        and lines[end].strip() == ""
        and start > 0
        and lines[start - 1].strip() == ""
    ):
        end += 1
    return "\n".join(lines[:start] + lines[end:])


def numbered_steps(section: ReportSection) -> list[tuple[int, int]]:
    """``(index_within_section_text, step_number)`` for ordered list items."""
    steps: list[tuple[int, int]] = []
    counter = 0
    for index, line in enumerate(section.text.splitlines()):
        if _NUMBERED_STEP_RE.match(line):
            counter += 1
            steps.append((index, counter))
    return steps


def step_lines(section: ReportSection) -> list[str]:
    return [line for line in section.text.splitlines() if _NUMBERED_STEP_RE.match(line)]


def _require_authorized(
    document: ReportDocument, section: ReportSection, *, expected_document_identity: str
) -> None:
    """Reject splices whose span provenance does not match this document.

    The expected identity must be captured with the span from its source
    document and carried by the caller; it is never re-derived from the
    target here (that comparison would be tautological).
    """
    if not span_authorized(
        document, section, expected_document_identity=expected_document_identity
    ):
        raise StaleSpanError(
            f"span {section.location} is not authorized for document "
            f"'{document.fixture_id}' (stale or foreign span)"
        )


def has_fence_marker(lines: list[str]) -> bool:
    """Whether any line opens (or closes) a fenced block (parser syntax)."""
    return any(_FENCE_RE.match(line) for line in lines)


def full_step_span(
    lines: list[str], steps: list[tuple[int, int]], pick_index: int
) -> set[int] | None:
    """Line offsets forming one list item: step line plus indented continuations.

    Returns the drop set including ``pick_index`` (offsets into ``lines``),
    or None when the item boundary is ambiguous: fence markers, heading
    lines, or non-indented neighbors in the continuation scan. Callers must
    take a controlled no-op instead of a partial edit. Blank lines are never
    dropped (neighbor spacing is preserved); sibling steps end the scan.
    """
    siblings = {index for index, _ in steps}
    drop = {pick_index}
    cursor = pick_index + 1
    while cursor < len(lines):
        line = lines[cursor]
        if not line.strip():
            cursor += 1
            continue
        if cursor in siblings:
            break
        if _FENCE_RE.match(line) or _HEADING_LINE_RE.match(line):
            return None
        if not line[:1].isspace():
            return None
        drop.add(cursor)
        cursor += 1
    return drop


def document_identity(document: ReportDocument) -> str:
    """Content identity of a document for span authorization (SHA-256 of raw bytes)."""
    return hashlib.sha256(document.raw_text.encode("utf-8")).hexdigest()


def span_authorized(
    document: ReportDocument,
    section: ReportSection,
    *,
    expected_document_identity: str,
) -> bool:
    """Check that ``section`` is an authorized span of ``document`` (E5a).

    A span is authorized exactly when the document's full-content identity
    matches the identity captured with the span, its location lies inside
    this document, the raw lines at that range rebuild the section text, and
    a headed section's first line parses to its heading. Pure check: no
    mutation behavior changes; operator-time enforcement is a later package.
    """
    if document_identity(document) != expected_document_identity:
        return False
    raw_lines = document.raw_text.splitlines()
    start = section.location.start_line
    end = section.location.end_line
    if not 1 <= start <= end <= len(raw_lines):
        return False
    if "\n".join(raw_lines[start - 1 : end]).strip("\n") != section.text:
        return False
    if section.heading is None:
        return start == 1
    match = _ATX_HEADING_RE.match(raw_lines[start - 1])
    if match is None:
        return False
    return match.group(2) == section.heading and len(match.group(1)) == section.level
