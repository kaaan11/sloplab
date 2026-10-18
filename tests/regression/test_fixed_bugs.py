"""Regression tests: minimal fixtures for every fixed bug (added as bugs close)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sloplab.corpus.loader import FixtureError, load_canonical_fixture
from sloplab.corpus.parser import parse_report
from sloplab.safety.policy import is_reserved_host
from tests._helpers import write_canonical_fixture


def test_regression_empty_preamble_after_leading_heading() -> None:
    """Bug: documents starting with an H1 produced a spurious empty preamble
    section, breaking section counting. Fixed by skipping empty preambles."""
    doc = parse_report("# Title\n\ntext\n", fixture_id="canonical-r-001", path="x")
    assert not [s for s in doc.sections if s.heading is None and not s.text.strip()]


@pytest.mark.parametrize("directory", ["sql-injection-003", "canonical-sql-injection-003"])
def test_regression_directory_name_suffix_matching(tmp_path: Path, directory: str) -> None:
    """Multi-dash IDs accept their full ID or the complete canonical suffix."""
    fixture = write_canonical_fixture(
        tmp_path, directory, fixture_id="canonical-sql-injection-003", title="SQL injection"
    )
    loaded = load_canonical_fixture(fixture, tmp_path)
    assert loaded.manifest.id == "canonical-sql-injection-003"


@pytest.mark.parametrize("directory", ["injection-003", "003", "unrelated"])
def test_regression_directory_name_mismatch(tmp_path: Path, directory: str) -> None:
    fixture = write_canonical_fixture(
        tmp_path, directory, fixture_id="canonical-sql-injection-003", title="SQL injection"
    )
    with pytest.raises(FixtureError, match="does not match directory name"):
        load_canonical_fixture(fixture, tmp_path)


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
