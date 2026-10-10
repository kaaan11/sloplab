"""Report document model: parsed Markdown plus source locations."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field


class SourceLocation(BaseModel):
    """1-indexed inclusive line range within the originating Markdown file."""

    model_config = ConfigDict(frozen=True)

    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    def contains(self, line: int) -> bool:
        return self.start_line <= line <= self.end_line


class ReportSection(BaseModel):
    """A single top-level-or-deeper Markdown section delimited by ATX headings."""

    model_config = ConfigDict(frozen=True)

    heading: str | None  # None only for preamble content before the first heading
    level: int = Field(ge=0, le=6)
    location: SourceLocation
    text: str


class ReportDocument(BaseModel):
    """Parsed representation of one vulnerability-report Markdown file."""

    model_config = ConfigDict(frozen=True)

    fixture_id: str
    title: str
    path: str  # display path relative to repo/corpus root
    raw_text: str
    sections: tuple[ReportSection, ...]

    def find_sections(self, pattern: str) -> list[ReportSection]:
        """Sections whose heading matches ``pattern`` (case-insensitive regex search)."""
        rx = re.compile(pattern, re.IGNORECASE)
        return [s for s in self.sections if s.heading is not None and rx.search(s.heading)]

    def section_text(self, pattern: str) -> str:
        """Concatenated text of sections matching ``pattern``; empty if none match."""
        return "\n".join(s.text for s in self.find_sections(pattern)).strip()

    def full_text(self) -> str:
        return self.raw_text
