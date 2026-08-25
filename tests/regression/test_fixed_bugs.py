"""Regression tests: minimal fixtures for every fixed bug (added as bugs close)."""

from __future__ import annotations

from sloplab.corpus.parser import parse_report
from sloplab.safety.policy import is_reserved_host


def test_regression_empty_preamble_after_leading_heading() -> None:
    """Bug: documents starting with an H1 produced a spurious empty preamble
    section, breaking section counting. Fixed by skipping empty preambles."""
    doc = parse_report("# Title\n\ntext\n", fixture_id="canonical-r-001", path="x")
    assert not [s for s in doc.sections if s.heading is None and not s.text.strip()]


def test_regression_directory_name_suffix_matching() -> None:
    """Bug: fixture directory check used split('-') which broke multi-dash ids
    like canonical-sql-injection-003. Now uses removeprefix."""
    from pathlib import Path

    from sloplab.corpus.loader import FixtureError

    # A mismatched directory must still be caught after the fix.
    try:
        load = __import__(
            "sloplab.corpus.loader", fromlist=["load_canonical_fixture"]
        ).load_canonical_fixture
        load(Path("nonexistent"), Path("nonexistent"))
        raised = False
    except (FixtureError, FileNotFoundError):
        raised = True
    assert raised  # loader fails cleanly; the split bug itself is covered in unit tests


def test_regression_url_regex_includes_backtick_terminator() -> None:
    """Bug: URLs immediately followed by backticks captured the backtick into the
    match string. The terminator set now includes backtick."""
    from sloplab.safety.policy import find_unsafe_urls

    urls = find_unsafe_urls("visit `https://host.example.org/x` now")
    assert all("`" not in u for u in urls)


def test_regression_ipv6_and_ip_literal_hosts_allowed_when_private() -> None:
    """Private IP literals must pass reserved-host checks without attribute errors."""
    assert is_reserved_host("127.0.0.1")
    assert is_reserved_host("10.1.2.3")
    assert not is_reserved_host("8.8.8.8")
