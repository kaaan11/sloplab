"""Corpus loading, parsing, and validation."""

from sloplab.corpus.conventions import DEFAULT_REQUIRED_EVIDENCE, EVIDENCE_SECTION_PATTERNS
from sloplab.corpus.loader import (
    CANONICAL_MANIFEST_NAME,
    MUTATION_MANIFEST_NAME,
    CanonicalFixture,
    DerivedFixture,
    FixtureError,
    discover_fixtures,
    format_validation_error,
    load_canonical_fixture,
    load_derived_fixture,
)
from sloplab.corpus.parser import parse_report
from sloplab.corpus.validation import ValidationResult, validate_corpus

__all__ = [
    "CANONICAL_MANIFEST_NAME",
    "MUTATION_MANIFEST_NAME",
    "CanonicalFixture",
    "DEFAULT_REQUIRED_EVIDENCE",
    "DerivedFixture",
    "EVIDENCE_SECTION_PATTERNS",
    "FixtureError",
    "ValidationResult",
    "discover_fixtures",
    "format_validation_error",
    "load_canonical_fixture",
    "load_derived_fixture",
    "parse_report",
    "validate_corpus",
]
