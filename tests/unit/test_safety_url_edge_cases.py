"""Comprehensive security policy tests: SSRF vectors, RFC 2606 compliance, and CVE namespaces."""

from __future__ import annotations

import pytest

from sloplab.safety.policy import (
    find_real_year_cves,
    find_unsafe_urls,
    is_reserved_host,
    validate_content_safety,
)


@pytest.mark.parametrize(
    ("host", "expected_reserved"),
    [
        # RFC 2606 and subdomains
        ("example.com", True),
        ("api.example.org", True),
        ("deep.nested.sub.example.net", True),
        ("example.edu", True),
        # Localhost and suffixes
        ("localhost", True),
        ("service.localhost", True),
        ("app.local", True),
        # Private/loopback IPs
        ("127.0.0.1", True),
        ("127.0.1.10", True),
        ("10.0.0.5", True),
        ("192.168.1.100", True),
        ("172.16.5.2", True),
        ("169.254.1.1", True),
        ("::1", True),
        # Unsafe public hosts
        ("google.com", False),
        ("github.com", False),
        ("8.8.8.8", False),
        ("1.1.1.1", False),
        ("142.250.190.46", False),
        # Bypass attempts
        ("evil-localhost.com", False),
        ("localhost.evil.com", False),
        ("notexample.com", False),
        ("example.com.attacker.com", False),
        ("attacker-example.org", False),
    ],
)
def test_is_reserved_host_matrix(host: str, expected_reserved: bool) -> None:
    assert is_reserved_host(host) is expected_reserved


def test_url_extraction_with_credentials_and_ports() -> None:
    safe_text = (
        "Safe URLs: https://user:secret@example.com:8443/api/v1 "
        "and http://localhost:3000/health "
        "and http://10.0.1.5:8080/metrics"
    )
    assert find_unsafe_urls(safe_text) == []
    assert validate_content_safety(safe_text) == []

    unsafe_text = (
        "Unsafe URLs: https://user:pass@evil.com:9000/exfil "
        "and http://8.8.8.8:53/dns "
        "and https://attacker.com/steal"
    )
    violations = find_unsafe_urls(unsafe_text)
    assert len(violations) == 3
    assert any("evil.com" in u for u in violations)
    assert any("8.8.8.8" in u for u in violations)
    assert any("attacker.com" in u for u in violations)


def test_cve_year_namespace_enforcement() -> None:
    safe_text = "Referencing synthetic issue CVE-2099-1001 and CVE-2099-99999"
    assert find_real_year_cves(safe_text) == []
    assert validate_content_safety(safe_text) == []

    unsafe_text = (
        "Comparing with real-world vulnerabilities CVE-2021-44228 (Log4Shell) "
        "and CVE-2023-38606 and CVE-2014-0160 (Heartbleed)"
    )
    real_cves = find_real_year_cves(unsafe_text)
    assert len(real_cves) == 3
    assert "CVE-2021-44228" in real_cves
    assert "CVE-2023-38606" in real_cves
    assert "CVE-2014-0160" in real_cves

    violations = validate_content_safety(unsafe_text)
    assert len(violations) == 3
