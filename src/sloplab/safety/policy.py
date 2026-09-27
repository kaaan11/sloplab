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
from collections.abc import Iterator
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

_FAKE_CVE_RE = re.compile(rf"CVE-{FAKE_CVE_YEAR}-\d{{4,}}", re.IGNORECASE)
_ANY_CVE_RE = re.compile(r"CVE-(\d{4})-\d{4,}", re.IGNORECASE)
_URL_CONTROL_WHITESPACE = "\t\r\n"
_URL_START_RE = re.compile(
    r"h[\t\r\n]*t[\t\r\n]*t[\t\r\n]*p(?:[\t\r\n]*s)?[\t\r\n]*:[\t\r\n]*/[\t\r\n]*/",
    re.IGNORECASE,
)
_URL_STOP_CHARS = frozenset(("<", ">", "(", ")", "`", '"', "'"))

_LOCAL_HOST_SUFFIXES = (".localhost", ".local")
_TRAILING_URL_PUNCTUATION = ".,;!?\"'*_~"


def _userinfo_separator_index(text: str, start: int) -> int | None:
    """Return the last @ before the authority ends.

    Brackets and prose-like punctuation before that separator are userinfo data,
    not host syntax. IPv6 bracket semantics only matter after userinfo has ended.
    """
    last_at: int | None = None
    cursor = start
    while cursor < len(text):
        char = text[cursor]
        if char in "/?#":
            break
        if char == "@":
            last_at = cursor
        cursor += 1
    return last_at


def _authority_control_run(text: str, start: int) -> tuple[bool, int]:
    """Return (continues_authority, first_non_control_index) for one control run.

    TAB/CR/LF are removed by browser URL parsing, but Markdown line breaks also
    delimit prose. Treat the run as URL-internal only when what follows still
    looks authority-like; consume the whole run once so adversarial inputs stay
    linear-time.
    """
    cursor = start
    line_breaks = 0
    while cursor < len(text) and text[cursor] in _URL_CONTROL_WHITESPACE:
        char = text[cursor]
        if char == "\r":
            line_breaks += 1
            cursor += 1
            if cursor < len(text) and text[cursor] == "\n":
                cursor += 1
            continue
        if char == "\n":
            line_breaks += 1
        cursor += 1

    # SlopLab validates Markdown source, not an already-concatenated browser URL.
    # A blank line is a paragraph boundary and therefore ends a lexical URL.
    if line_breaks >= 2:
        return False, cursor
    if cursor >= len(text):
        return False, cursor
    next_char = text[cursor]
    if next_char in ".@:":
        return True, cursor
    if next_char.isspace() or next_char in _URL_STOP_CHARS or next_char in "/?#":
        return False, cursor

    end = cursor
    while end < len(text):
        char = text[end]
        if char.isspace() or char in _URL_STOP_CHARS or char in "/?#":
            break
        end += 1
    segment = text[cursor:end]
    if not segment:
        return False, cursor
    # Any contiguous non-delimiter text can extend the authority after a
    # browser-normalized TAB/CR/LF run (for example localhost\nattacker).
    # Keep it in the candidate and fail closed rather than approving a safe
    # prefix. Markdown headings/path/query/fragment delimiters were rejected
    # above and remain prose/URL boundaries.
    return True, cursor


def _stop_char_is_prose_boundary(text: str, index: int) -> bool:
    """Whether a quote/bracket-like stop char actually ends surrounding prose.

    Delimiters may be legal userinfo/host bytes for browser URL parsers. Treat
    them as prose closers only when every following wrapper/punctuation byte
    reaches whitespace or end-of-text. If authority-like text resumes after
    that punctuation run, keep the delimiter inside the candidate and fail
    closed instead of approving a safe prefix.
    """
    cursor = index + 1
    if cursor >= len(text):
        return True
    if text[cursor].isspace():
        return True
    trailing = set(_TRAILING_URL_PUNCTUATION) | set(_URL_STOP_CHARS) | {"]"}
    while cursor < len(text) and text[cursor] in trailing:
        cursor += 1
    return cursor >= len(text) or text[cursor].isspace()


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


def _iter_url_tokens(text: str) -> Iterator[str]:
    """Yield disjoint HTTP(S) tokens while preserving bracketed IPv6 hosts."""
    cursor = 0
    while match := _URL_START_RE.search(text, cursor):
        start = match.start()
        end = match.end()
        bracket_depth = 0
        authority_done = False
        userinfo_separator = _userinfo_separator_index(text, match.end())
        scan = match.end()
        while scan < len(text):
            char = text[scan]
            if char.isspace():
                in_userinfo_space = (
                    userinfo_separator is not None
                    and scan < userinfo_separator
                    and not authority_done
                )
                if char not in _URL_CONTROL_WHITESPACE:
                    if not in_userinfo_space:
                        break
                    scan += 1
                    end = scan
                    continue
                if authority_done:
                    break
                continues, control_end = _authority_control_run(text, scan)
                if not continues and not in_userinfo_space:
                    break
                scan = control_end
                end = scan
                continue
            in_userinfo = userinfo_separator is not None and scan < userinfo_separator
            if char in _URL_STOP_CHARS:
                if authority_done:
                    break
                if not in_userinfo and _stop_char_is_prose_boundary(text, scan):
                    break
            if char == "[":
                if not in_userinfo:
                    bracket_depth += 1
            elif char == "]":
                if not in_userinfo:
                    if bracket_depth == 0:
                        break
                    bracket_depth -= 1
            elif bracket_depth == 0 and char in "/?#":
                authority_done = True
            scan += 1
            end = scan
        token = text[start:end].rstrip(_TRAILING_URL_PUNCTUATION)
        if token:
            yield token
        # The scanned token and any embedded scheme-like substrings form one
        # lexical URL. Resume at its boundary rather than rescanning suffixes.
        cursor = max(scan, match.end())


def find_unsafe_urls(text: str) -> list[str]:
    """URLs whose parsed hostname is outside approved local/reserved namespaces."""
    unsafe: set[str] = set()
    for url in _iter_url_tokens(text):
        if (
            "\\" in url
            or any(control in url for control in _URL_CONTROL_WHITESPACE)
            or any(delimiter in url for delimiter in _URL_STOP_CHARS)
        ):
            unsafe.add(url)
            continue
        try:
            host = urlsplit(url).hostname
        except ValueError:
            host = None
        if host is None or not is_reserved_host(host):
            unsafe.add(url)
    return sorted(unsafe)


def validate_content_safety(text: str) -> list[str]:
    """Return a list of safety violations in ``text`` (empty means compliant)."""
    violations: list[str] = []
    for cve in find_real_year_cves(text):
        violations.append(f"non-reserved CVE reference (only CVE-{FAKE_CVE_YEAR}-* allowed): {cve}")
    for url in find_unsafe_urls(text):
        violations.append(f"URL outside reserved domains {RESERVED_DOMAINS}: {url}")
    return violations
