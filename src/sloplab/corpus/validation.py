"""Corpus-level validation: consistency, evidence coverage, and safety policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sloplab.corpus.conventions import EVIDENCE_SECTION_PATTERNS
from sloplab.corpus.loader import CanonicalFixture, DerivedFixture
from sloplab.safety.policy import validate_content_safety


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    location: str
    message: str

    def render(self) -> str:
        return f"[{self.severity}] {self.location}: {self.message}"


@dataclass
class ValidationResult:
    checked_canonical: int = 0
    checked_derived: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, location: str, message: str) -> None:
        self.issues.append(ValidationIssue("error", location, message))

    def warn(self, location: str, message: str) -> None:
        self.issues.append(ValidationIssue("warning", location, message))

    def render(self) -> str:
        lines = [
            f"canonical fixtures checked: {self.checked_canonical}",
            f"derived cases checked: {self.checked_derived}",
            f"errors: {len(self.errors)}  warnings: {len(self.warnings)}",
        ]
        lines.extend(issue.render() for issue in self.issues)
        return "\n".join(lines)


def validate_canonical_fixture(fixture: CanonicalFixture, result: ValidationResult) -> None:
    loc = str(fixture.directory)
    manifest = fixture.manifest
    text = fixture.report.raw_text

    # Evidence coverage: every required_evidence key must map to a known section.
    for key in manifest.ground_truth.required_evidence:
        pattern = EVIDENCE_SECTION_PATTERNS.get(key)
        if pattern is None:
            result.error(
                loc,
                f"unknown required_evidence key '{key}'; "
                f"known keys: {sorted(EVIDENCE_SECTION_PATTERNS)}",
            )
            continue
        if not fixture.report.find_sections(pattern):
            result.error(loc, f"required evidence section missing for key '{key}'")

    # Safety: canonical fixtures must also stay within reserved namespaces.
    for violation in validate_content_safety(text):
        result.error(loc, f"safety violation: {violation}")

    # Valid-class fixtures should be marked reproducible.
    if manifest.report_class.value == "valid" and manifest.ground_truth.reproducible is not True:
        result.warn(loc, "valid-class fixture usually has ground_truth.reproducible: true")

    # Presentation pairs need a sibling with the same pair_id (checked at corpus level).


def validate_derived_fixture(fixture: DerivedFixture, result: ValidationResult) -> None:
    loc = str(fixture.directory)
    for violation in validate_content_safety(fixture.report.raw_text):
        result.error(loc, f"safety violation: {violation}")
    if not fixture.manifest.parent_id.startswith("canonical-"):
        result.error(loc, f"invalid parent_id '{fixture.manifest.parent_id}'")


def validate_pairing(canonical: list[CanonicalFixture], result: ValidationResult) -> None:
    pairs: dict[str, list[str]] = {}
    for fixture in canonical:
        pair_id = fixture.manifest.pair_id
        if pair_id:
            pairs.setdefault(pair_id, []).append(fixture.manifest.id)
    for pair_id, members in sorted(pairs.items()):
        if len(members) != 2:
            result.error(
                f"pair:{pair_id}",
                f"presentation pair must contain exactly 2 members, got {len(members)}",
            )


def validate_corpus(
    canonical: list[CanonicalFixture],
    derived: list[DerivedFixture],
    corpus_root: Path | None = None,
) -> ValidationResult:
    result = ValidationResult()
    result.checked_canonical = len(canonical)
    result.checked_derived = len(derived)
    for canon in canonical:
        validate_canonical_fixture(canon, result)
    for derived_case in derived:
        validate_derived_fixture(derived_case, result)
    validate_pairing(canonical, result)
    _ = corpus_root
    return result
