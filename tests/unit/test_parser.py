"""Tests for the Markdown report parser (source locations, fences, sections)."""

from sloplab.corpus.conventions import EVIDENCE_SECTION_PATTERNS
from sloplab.corpus.parser import parse_report

SAMPLE = """\
# Missing authorization in DemoVault

Some summary text here.

## Affected Component

DemoVault web module.

## Reproduction Steps

```bash
# this comment is inside a fence
curl https://api.example.com/objects/42
```

1. Log in as low-privilege user.
2. Request another tenant's object.

## Observed Result

Object returned without authorization check.
"""


def test_title_from_first_h1() -> None:
    doc = parse_report(SAMPLE, fixture_id="canonical-test-001", path="x/report.md")
    assert doc.title == "Missing authorization in DemoVault"


def test_sections_preserve_line_numbers() -> None:
    doc = parse_report(SAMPLE, fixture_id="canonical-test-001", path="x/report.md")
    repro = doc.find_sections(r"reproduction")[0]
    # "## Reproduction Steps" is line 9 in SAMPLE
    assert repro.location.start_line == 9
    observed = doc.find_sections(r"observed")[0]
    assert observed.location.start_line == 19


def test_fenced_hash_lines_are_not_headings() -> None:
    doc = parse_report(SAMPLE, fixture_id="canonical-test-001", path="x/report.md")
    headings = [s.heading for s in doc.sections if s.heading]
    assert all("comment" not in h.lower() for h in headings)
    assert len(doc.sections) == 4  # preamble + 3 headed sections


def test_section_text_contains_body() -> None:
    doc = parse_report(SAMPLE, fixture_id="canonical-test-001", path="x/report.md")
    text = doc.section_text(r"observed")
    assert "without authorization check" in text


def test_content_after_h1_belongs_to_h1_section() -> None:
    doc = parse_report(SAMPLE, fixture_id="canonical-test-001", path="x/report.md")
    h1 = doc.find_sections(r"^Missing authorization")[0]
    assert "Some summary text here." in h1.text


def test_text_before_first_heading_is_preamble() -> None:
    doc = parse_report(
        "Intro paragraph.\n\n## Section A\n\nbody\n",
        fixture_id="canonical-test-002",
        path="x/report.md",
    )
    preamble = [s for s in doc.sections if s.heading is None]
    assert len(preamble) == 1
    assert "Intro paragraph." in preamble[0].text


def test_document_starting_with_heading_has_no_preamble() -> None:
    doc = parse_report("# Title\n\ntext\n", fixture_id="canonical-test-003", path="x/report.md")
    assert all(s.heading is not None or s.text for s in doc.sections)
    assert not any(s.heading is None and not s.text.strip() for s in doc.sections)


def test_document_without_h1_falls_back_to_fixture_id() -> None:
    doc = parse_report("## Only H2\n\ntext\n", fixture_id="canonical-x-001", path="y.md")
    assert doc.title == "canonical-x-001"


def test_shorter_or_different_fence_does_not_close_code_block() -> None:
    raw = """# Title

~~~~bash
~~~ 
## Still inside fence
```
## Also inside fence
~~~~

## Real Section

body
"""
    doc = parse_report(raw, fixture_id="canonical-fence-001", path="x.md")
    headings = [section.heading for section in doc.sections if section.heading is not None]
    assert "Still inside fence" not in headings
    assert "Also inside fence" not in headings
    assert "Real Section" in headings


def test_atx_closing_hashes_do_not_strip_csharp_title() -> None:
    raw = "# C#\n\n## Details ###\n\nbody\n"
    doc = parse_report(raw, fixture_id="canonical-heading-001", path="x.md")
    assert doc.title == "C#"
    headings = [section.heading for section in doc.sections if section.heading is not None]
    assert "Details" in headings


def test_plural_expected_security_boundaries_heading_is_recognized() -> None:
    raw = "# T\n\n## Expected Security Boundaries\n\nTenant isolation applies.\n"
    doc = parse_report(raw, fixture_id="canonical-boundary-001", path="x.md")
    matches = doc.find_sections(EVIDENCE_SECTION_PATTERNS["expected_security_boundary"])
    assert len(matches) == 1
    assert matches[0].heading == "Expected Security Boundaries"
