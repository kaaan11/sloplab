"""Safety policy: approved identifier namespaces and content validators.

All fabricated identifiers emitted anywhere in SlopLab (fixtures, mutation output)
must come from the namespaces below. See docs/safety.md (D-0003).

Allowed URL hosts are: RFC 2606 reserved domains (+ subdomains), ``localhost``
variants, and private/loopback/link-local IP literals (RFC 1918 / 127.0.0.0/8 /
169.254.0.0/16). Public hosts would risk pointing at real targets and are rejected.
"""

from __future__ import annotations

import ipaddress
import re

#: Fictional far-future year for all fabricated CVE references.
FAKE_CVE_YEAR = "2099"

#: RFC 2606 reserved documentation domains allowed in generated text.
RESERVED_DOMAINS: tuple[str, ...] = (
    "example.com",
    "example.org",
    "example.net",
    "example.edu",
)

#: Fixed synthetic product/component names usable in fixtures and mutations.
SYNTHETIC_PRODUCTS: tuple[str, ...] = (
    "AcmePortal",
    "DemoVault",
    "SampleStack",
    "ToyTracker",
    "MockMart",
    "PlaygroundAPI",
    "SandboxSuite",
    "ExampleApp",
)

#: Fixed synthetic person names for attribution-style mutations.
SYNTHETIC_PERSONS: tuple[str, ...] = (
    "A. Tester",
    "B. Researcher",
    "C. Analyst",
    "D. Reviewer",
)

_FAKE_CVE_RE = re.compile(rf"CVE-{FAKE_CVE_YEAR}-\d{{4,}}")
_ANY_CVE_RE = re.compile(r"CVE-(\d{4})-\d{4,}")
_URL_RE = re.compile(r"https?://(?P<host>[A-Za-z0-9.-]+)[^\s)\]>`]*", re.IGNORECASE)

_LOCAL_HOST_SUFFIXES = ("localhost", ".localhost", ".local")


def is_reserved_host(host: str) -> bool:
    """True if host is a reserved documentation domain, localhost, or private IP."""
    host = host.lower().rstrip(".")
    if any(host == suffix or host.endswith(suffix) for suffix in _LOCAL_HOST_SUFFIXES):
        return True
    if any(host == d or host.endswith("." + d) for d in RESERVED_DOMAINS):
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_reserved


def find_real_year_cves(text: str) -> list[str]:
    """CVE references whose year is not the fictional 2099 namespace."""
    return sorted(
        {match.group(0) for match in _ANY_CVE_RE.finditer(text) if match.group(1) != FAKE_CVE_YEAR}
    )


def find_unsafe_urls(text: str) -> list[str]:
    """URLs whose host is outside reserved domains and private/loopback addresses."""
    unsafe: set[str] = set()
    for match in _URL_RE.finditer(text):
        if not is_reserved_host(match.group("host")):
            unsafe.add(match.group(0))
    return sorted(unsafe)


def validate_content_safety(text: str) -> list[str]:
    """Return a list of safety violations in ``text`` (empty means compliant)."""
    violations: list[str] = []
    for cve in find_real_year_cves(text):
        violations.append(f"non-reserved CVE reference (only CVE-{FAKE_CVE_YEAR}-* allowed): {cve}")
    for url in find_unsafe_urls(text):
        violations.append(f"URL outside reserved domains {RESERVED_DOMAINS}: {url}")
    return violations
