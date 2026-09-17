"""Line-span editing utilities for mutating parsed reports deterministically."""

from __future__ import annotations

import re

from sloplab.models.report import ReportDocument, ReportSection

_NUMBERED_STEP_RE = re.compile(r"^\s*\d+[.)]\s+")


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
