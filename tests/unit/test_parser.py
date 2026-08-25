"""Tests for the Markdown report parser (source locations, fences, sections)."""

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


def test_preamble_section_has_no_heading() -> None:
    doc = parse_report(SAMPLE, fixture_id="canonical-test-001", path="x/report.md")
    preamble = [s for s in doc.sections if s.heading is None]
    assert len(preamble) == 1
    assert "Some summary text here." in preamble[0].text


def test_document_without_h1_falls_back_to_fixture_id() -> None:
    doc = parse_report("## Only H2\n\ntext\n", fixture_id="canonical-x-001", path="y.md")
    assert doc.title == "canonical-x-001"
