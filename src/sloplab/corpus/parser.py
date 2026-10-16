"""Deterministic Markdown parser preserving source line locations.

Reports are structured with ATX headings. Fenced code blocks are tracked so that
``#``-prefixed lines inside them are never treated as headings.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from sloplab.models.report import ReportDocument, ReportSection, SourceLocation

_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})(?:[ \t]+(?P<text>.*)|$)")
_ATX_CLOSING_RE = re.compile(r"[ \t]+#+[ \t]*$")
_FENCE_RE = re.compile(r"^\s*(?P<fence>`{3,}|~{3,})")


def iter_fenced_lines(text: str) -> Iterator[tuple[bool, str]]:
    """Yield lines with their fence status, including both delimiter lines.

    Backtick and tilde fences close only on the same character, at least the
    opening length, followed by whitespace alone. Unclosed fences protect the
    rest of the document.
    """
    fence_marker = ""
    fence_length = 0
    for line in text.splitlines():
        match = _FENCE_RE.match(line)
        if fence_marker:
            yield True, line
            if match:
                marker = match.group("fence")
                if (
                    marker[0] == fence_marker
                    and len(marker) >= fence_length
                    and not line[match.end() :].strip()
                ):
                    fence_marker = ""
                    fence_length = 0
        elif match:
            marker = match.group("fence")
            fence_marker, fence_length = marker[0], len(marker)
            yield True, line
        else:
            yield False, line


def parse_report(
    raw_text: str,
    *,
    fixture_id: str,
    path: str,
) -> ReportDocument:
    """Parse Markdown text into a ReportDocument with per-section line ranges."""
    lines = raw_text.splitlines()
    sections: list[ReportSection] = []
    current_heading: str | None = None
    current_level = 0
    section_start = 1

    def close_section(end_line: int) -> None:
        body = "\n".join(lines[section_start - 1 : end_line]).strip("\n")
        sections.append(
            ReportSection(
                heading=current_heading,
                level=current_level,
                location=SourceLocation(
                    start_line=section_start, end_line=max(section_start, end_line)
                ),
                text=body,
            )
        )

    for index, (in_fence, line) in enumerate(iter_fenced_lines(raw_text), start=1):
        if in_fence:
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            # Skip an empty preamble when the document starts with a heading.
            if not (current_heading is None and section_start > index - 1):
                close_section(index - 1)
            heading_text = (heading_match.group("text") or "").rstrip(" \t")
            if re.fullmatch(r"#+", heading_text):
                heading_text = ""
            else:
                heading_text = _ATX_CLOSING_RE.sub("", heading_text).rstrip(" \t")
            current_heading = heading_text
            current_level = len(heading_match.group("hashes"))
            section_start = index

    close_section(len(lines))

    title = next((s.heading for s in sections if s.level == 1 and s.heading), fixture_id)

    return ReportDocument(
        fixture_id=fixture_id,
        title=title or fixture_id,
        path=path,
        raw_text=raw_text,
        sections=tuple(sections),
    )
