"""Line-span editing utilities for mutating parsed reports deterministically."""

from __future__ import annotations

import hashlib
import re

from sloplab.models.report import ReportDocument, ReportSection

_NUMBERED_STEP_RE = re.compile(r"^\s*\d+[.)]\s+")
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def first_matching_section(document: ReportDocument, pattern: str) -> ReportSection | None:
    matches = document.find_sections(pattern)
    return matches[0] if matches else None


def replace_section_body(document: ReportDocument, section: ReportSection, new_body: str) -> str:
    """Render the document with one section's body replaced (heading preserved).

    ``new_body`` may be empty, which leaves only the heading.
    """
    lines = document.raw_text.splitlines()
    prefix = lines[: section.location.start_line]  # through the heading line
    replacement = new_body.splitlines() if new_body else []
    suffix = lines[section.location.end_line :]
    return "\n".join(prefix + replacement + suffix)


def remove_section(document: ReportDocument, section: ReportSection) -> str:
    """Render the document with an entire section (heading and body) removed."""
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
