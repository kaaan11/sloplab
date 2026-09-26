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
from urllib.parse import urlsplit

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
_ANY_CVE_RE = re.compile(r"CVE-(\d{4})-\d{4,}", re.IGNORECASE)
_URL_RE = re.compile(r"https?://(?![/\\])[^\s)>`]+", re.IGNORECASE)
_URL_SCHEME_RE = re.compile(
    r"h[\t\r\n]*t[\t\r\n]*t[\t\r\n]*p[\t\r\n]*(?:s[\t\r\n]*)?:",
    re.IGNORECASE,
)
_AUTHORITY_DELIMITERS = frozenset(" \f\v/?#)>`")

_LOCAL_HOST_SUFFIXES = (".localhost", ".local")


def is_reserved_host(host: str) -> bool:
    """True if host is a reserved documentation domain, localhost, or private IP."""
    host = host.lower().rstrip(".")
    if host == "localhost" or any(host.endswith(suffix) for suffix in _LOCAL_HOST_SUFFIXES):
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


def _trim_url_candidate(url: str) -> str:
    """Remove prose delimiters without damaging a balanced bracketed IPv6 host."""
    url = url.rstrip(".,;!?'\"*_~")
    while url.endswith("]") and url.count("]") > url.count("["):
        url = url[:-1]
    return url


def _special_url_candidates(text: str) -> list[tuple[str, str]]:
    """Return non-standard HTTP(S) spellings and a canonical URL for host checks.

    WHATWG special schemes tolerate missing/extra slashes, backslash separators,
    and TAB/CR/LF controls. This scanner handles those forms without letting a
    single Markdown blank line merge unrelated prose into an authority.
    """
    candidates: list[tuple[str, str]] = []
    for match in _URL_SCHEME_RE.finditer(text):
        scheme_raw = match.group(0)
        scheme = scheme_raw.replace("\t", "").replace("\r", "").replace("\n", "")
        cursor = match.end()
        prefix_nonstandard = any(char in "\t\r\n" for char in scheme_raw)
        separators: list[str] = []
        boundary = False

        while cursor < len(text):
            char = text[cursor]
            if char == "\t":
                prefix_nonstandard = True
                cursor += 1
                continue
            if char in "\r\n":
                end = cursor + 1
                if char == "\r" and end < len(text) and text[end] == "\n":
                    end += 1
                if end < len(text) and text[end] in "\r\n":
                    boundary = True
                    break
                prefix_nonstandard = True
                cursor = end
                continue
            if char in "/\\":
                separators.append(char)
                cursor += 1
                continue
            break

        if boundary:
            continue
        if separators != ["/", "/"]:
            prefix_nonstandard = True

        authority_start = cursor
        authority_control = False
        while cursor < len(text):
            char = text[cursor]
            if char in _AUTHORITY_DELIMITERS or char == "\\":
                break
            if char == "\t":
                authority_control = True
                cursor += 1
                continue
            if char in "\r\n":
                end = cursor + 1
                if char == "\r" and end < len(text) and text[end] == "\n":
                    end += 1
                if end < len(text) and text[end] in "\r\n":
                    break
                authority_control = True
                cursor = end
                continue
            cursor += 1

        authority_raw = text[authority_start:cursor]
        authority = _trim_url_candidate(
            authority_raw.replace("\t", "").replace("\r", "").replace("\n", "")
        )
        if not authority or not (prefix_nonstandard or authority_control):
            continue

        raw = _trim_url_candidate(text[match.start() : cursor])
        candidates.append((raw, f"{scheme}//{authority}"))
    return candidates


def find_unsafe_urls(text: str) -> list[str]:
    """URLs whose host is outside reserved domains and private/loopback addresses."""
    unsafe: set[str] = set()
    for raw, canonical in _special_url_candidates(text):
        display_url = raw.replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")
        try:
            host = urlsplit(canonical).hostname
        except ValueError:
            host = None
        if host is None or not is_reserved_host(host):
            unsafe.add(display_url)

    for match in _URL_RE.finditer(text):
        url = _trim_url_candidate(match.group(0))
        authority = url.split("://", 1)[1]
        authority = re.split(r"[/\?#]", authority, maxsplit=1)[0]
        display_url = url.replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")
        if "\\" in authority:
            unsafe.add(display_url)
            continue
        try:
            host = urlsplit(url).hostname
        except ValueError:
            host = None
        if host is None or not is_reserved_host(host):
            unsafe.add(display_url)
    return sorted(unsafe)


def validate_content_safety(text: str) -> list[str]:
    """Return a list of safety violations in ``text`` (empty means compliant)."""
    violations: list[str] = []
    for cve in find_real_year_cves(text):
        violations.append(f"non-reserved CVE reference (only CVE-{FAKE_CVE_YEAR}-* allowed): {cve}")
    for url in find_unsafe_urls(text):
        violations.append(f"URL outside reserved domains {RESERVED_DOMAINS}: {url}")
    return violations
