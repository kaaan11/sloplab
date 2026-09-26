"""Issue #18: safety URL authority parsing and CVE matching regressions."""

from __future__ import annotations

import pytest

from sloplab.safety.policy import find_real_year_cves, find_unsafe_urls, validate_content_safety


def test_url_userinfo_does_not_hide_external_hostname() -> None:
    url = "http://localhost@attacker.com/payload"
    assert find_unsafe_urls(url) == [url]
    assert validate_content_safety(url)


def test_url_userinfo_with_actual_localhost_is_allowed() -> None:
    assert find_unsafe_urls("http://demo-user@localhost:8080/path") == []


@pytest.mark.parametrize(
    "url",
    [
        "http://fakelocalhost/path",
        "http://localhost.attacker.example/path",
        "https://example.com.attacker.invalid/path",
    ],
)
def test_lookalike_local_or_reserved_hosts_are_rejected(url: str) -> None:
    assert find_unsafe_urls(url) == [url]


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/path",
        "http://api.localhost/path",
        "http://demo.local/path",
        "https://example.org/path",
        "https://deep.example.com/path",
        "http://127.0.0.1:9000/path",
        "http://10.0.0.5/path",
        "http://[::1]:8080/path",
    ],
)
def test_approved_hosts_remain_allowed(url: str) -> None:
    assert find_unsafe_urls(url) == []


def test_url_parser_strips_markdown_terminator_but_keeps_ipv6_brackets() -> None:
    assert find_unsafe_urls("[https://attacker.invalid/x].") == [
        "https://attacker.invalid/x"
    ]
    assert find_unsafe_urls("http://[::1]/health") == []


def test_lowercase_real_year_cve_is_detected() -> None:
    assert find_real_year_cves("see cve-2021-44228") == ["cve-2021-44228"]
    violations = validate_content_safety("see cve-2021-44228")
    assert len(violations) == 1
    assert "cve-2021-44228" in violations[0]


@pytest.mark.parametrize("value", ["CVE-2099-12345", "cve-2099-12345", "CvE-2099-12345"])
def test_fake_year_cve_is_allowed_case_insensitively(value: str) -> None:
    assert find_real_year_cves(value) == []
    assert validate_content_safety(value) == []
