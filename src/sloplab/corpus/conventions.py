"""Shared corpus conventions: standard section names and their heading patterns."""

from __future__ import annotations

import re

#: Evidence keys used in manifests mapped to case-insensitive heading patterns.
EVIDENCE_SECTION_PATTERNS: dict[str, str] = {
    "summary": r"summary|description|overview",
    "affected_component": r"affected\s+components?",
    "affected_versions": r"affected\s+versions?",
    "preconditions": r"preconditions?",
    "reproduction_steps": r"reproduction\s+steps?|steps\s+to\s+reproduce",
    "observed_result": r"observed\s+results?",
    "expected_security_boundary": r"expected\s+security\s+boundary",
}

#: Keys that canonical valid fixtures are expected to cover by default.
DEFAULT_REQUIRED_EVIDENCE: tuple[str, ...] = (
    "affected_component",
    "preconditions",
    "reproduction_steps",
    "observed_result",
    "expected_security_boundary",
)

COMPILED_EVIDENCE_PATTERNS: dict[str, re.Pattern[str]] = {
    key: re.compile(pattern, re.IGNORECASE) for key, pattern in EVIDENCE_SECTION_PATTERNS.items()
}


def resolve_evidence_pattern(key: str) -> re.Pattern[str] | None:
    return COMPILED_EVIDENCE_PATTERNS.get(key)
