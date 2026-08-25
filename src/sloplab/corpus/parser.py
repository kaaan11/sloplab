"""Deterministic Markdown parser preserving source line locations.

Reports are structured with ATX headings. Fenced code blocks are tracked so that
``#``-prefixed lines inside them are never treated as headings.
"""

from __future__ import annotations

import re

from sloplab.models.report import ReportDocument, ReportSection, SourceLocation

_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(?P<fence>`{3,}|~{3,})")


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
    in_fence = False
    fence_marker = ""

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

    for index, line in enumerate(lines, start=1):
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group("fence")
            if not in_fence:
                in_fence = True
                fence_marker = marker[0]
            elif marker[0] == fence_marker and len(marker) >= 3:
                in_fence = False
            continue

        if in_fence:
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            # Skip an empty preamble when the document starts with a heading.
            if not (current_heading is None and section_start > index - 1):
                close_section(index - 1)
            current_heading = heading_match.group("text").strip()
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
