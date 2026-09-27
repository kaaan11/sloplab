"""Issue #18: safety URL authority parsing and CVE matching regressions."""

from __future__ import annotations

import pytest

from sloplab.safety.policy import (
    _iter_url_tokens,
    find_real_year_cves,
    find_unsafe_urls,
    validate_content_safety,
)


def test_url_userinfo_does_not_hide_external_hostname() -> None:
    url = "http://localhost@attacker.com/payload"
    assert find_unsafe_urls(url) == [url]
    assert validate_content_safety(url)


def test_url_userinfo_with_actual_localhost_is_allowed() -> None:
    assert find_unsafe_urls("http://demo-user@localhost:8080/path") == []


def test_space_before_userinfo_separator_cannot_hide_external_host() -> None:
    url = "http://localhost @attacker.com/x"
    assert find_unsafe_urls(url) == [url]
    assert validate_content_safety(url)


def test_space_in_userinfo_with_actual_localhost_remains_allowed() -> None:
    assert find_unsafe_urls("http://demo user@localhost:8080/path") == []


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
    assert find_unsafe_urls("[https://attacker.invalid/x].") == ["https://attacker.invalid/x"]
    assert find_unsafe_urls("http://[::1]/health") == []


def test_browser_style_backslash_cannot_hide_external_hostname() -> None:
    url = r"http://attacker.com\@localhost/"
    assert find_unsafe_urls(url) == [url]
    assert validate_content_safety(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost\t@attacker.com/x",
        "http://localhost\n.attacker.com/x",
        "http://example.com\tpany/x",
        "http:\n\n//attacker.com/x",
        "h\tt\ntp://attacker.com/x",
    ],
)
def test_control_whitespace_cannot_hide_external_authority(url: str) -> None:
    assert find_unsafe_urls(url) == [url]
    assert validate_content_safety(url)


def test_control_whitespace_after_path_remains_a_text_boundary() -> None:
    text = "https://example.org/path\nNext paragraph"
    assert find_unsafe_urls(text) == []


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/a(b)c",
        "https://example.org/a'b",
        "https://example.org/path?q=(demo)",
    ],
)
def test_authority_delimiters_in_path_do_not_reject_reserved_host(url: str) -> None:
    assert find_unsafe_urls(url) == []


@pytest.mark.parametrize(
    "text",
    [
        "https://tracker.example.org/billing/invoices/<id>/download",
        "https://shop.example.org/api/search?q=<term>",
        "https://shop.example.org/login?next=<path>",
    ],
)
def test_path_and_query_placeholders_do_not_change_reserved_host(text: str) -> None:
    assert find_unsafe_urls(text) == []


def test_bare_safe_url_before_markdown_paragraph_break_is_not_merged() -> None:
    text = "Endpoint: https://demo.example.org.\n\n## Next section\n"
    assert find_unsafe_urls(text) == []


def test_bare_url_before_plain_prose_line_fails_closed() -> None:
    text = "Endpoint: https://example.org\nNext paragraph starts here."
    assert find_unsafe_urls(text) == ["https://example.org\nNext"]


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost\r\n.attacker.com/x",
        "http://localhost\nattacker.com/x",
    ],
)
def test_single_linebreak_with_authority_like_continuation_is_rejected(url: str) -> None:
    assert find_unsafe_urls(url) == [url]


@pytest.mark.parametrize(
    "text",
    [
        "http://localhost\n\nattacker.com/x",
        "http://localhost\n\t\nattacker.com/x",
    ],
)
def test_blank_line_is_a_markdown_url_boundary(text: str) -> None:
    assert find_unsafe_urls(text) == []


def test_long_tab_run_before_authority_continuation_is_rejected() -> None:
    url = "http://localhost" + ("\t" * 8_000) + ".attacker.com/x"
    assert find_unsafe_urls(url) == [url]


def test_control_run_before_delimiter_authority_continuation_is_rejected() -> None:
    url = "http://localhost\t'attacker.com/x"
    assert find_unsafe_urls(url) == [url]
    assert validate_content_safety(url)


def test_delimiter_before_control_authority_continuation_is_rejected() -> None:
    url = "http://localhost'\tattacker.com/x"
    assert find_unsafe_urls(url) == [url]
    assert validate_content_safety(url)


def test_long_delimiter_run_before_hostname_continuation_is_rejected() -> None:
    url = "http://localhost" + ("'" * 12_000) + "attacker.com/x"
    assert find_unsafe_urls(url) == [url]


def test_plain_hostname_continuation_after_newline_is_rejected() -> None:
    url = "http://localhost\nattacker"
    assert find_unsafe_urls(url) == [url]
    assert validate_content_safety(url)


@pytest.mark.parametrize("delimiter", ["'", '"', "`", "(", ")", "<", ">"])
def test_delimiter_joined_hostname_without_userinfo_is_rejected(delimiter: str) -> None:
    url = f"http://localhost{delimiter}attacker.com/x"
    assert find_unsafe_urls(url) == [url]
    assert validate_content_safety(url)


@pytest.mark.parametrize("delimiter", ["'", '"', "`", "(", ")", "<", ">"])
def test_delimiter_then_punctuation_cannot_hide_hostname_continuation(delimiter: str) -> None:
    url = f"http://localhost{delimiter}.attacker.com/x"
    assert find_unsafe_urls(url) == [url]
    assert validate_content_safety(url)


@pytest.mark.parametrize(
    "text",
    [
        '"http://localhost".',
        "'https://example.org', next",
        "<https://example.com>.",
        "(http://localhost), next",
    ],
)
def test_delimiter_punctuation_run_can_close_wrapped_prose_url(text: str) -> None:
    assert find_unsafe_urls(text) == []


@pytest.mark.parametrize("delimiter", ['"', "'", "`", "(", ")", "<", ">"])
def test_authority_delimiter_before_userinfo_cannot_hide_external_host(delimiter: str) -> None:
    url = f"http://localhost{delimiter}@attacker.com/x"
    assert find_unsafe_urls(url) == [url]
    assert validate_content_safety(url)


@pytest.mark.parametrize("bracket", ["[", "]"])
def test_bracket_before_userinfo_cannot_hide_external_host(bracket: str) -> None:
    url = f"http://localhost{bracket}@attacker.com/x"
    assert find_unsafe_urls(url) == [url]
    assert validate_content_safety(url)


def test_ipv6_brackets_after_userinfo_separator_remain_host_syntax() -> None:
    assert find_unsafe_urls("http://demo@[::1]:8080/path") == []


@pytest.mark.parametrize(
    "text",
    [
        '"http://localhost"',
        "'https://example.org'",
        "`http://127.0.0.1`",
        "<https://example.com>",
        "(http://localhost)",
    ],
)
def test_prose_delimiters_without_userinfo_remain_boundaries(text: str) -> None:
    assert find_unsafe_urls(text) == []


@pytest.mark.parametrize(
    "text", ["**http://localhost**", "__https://example.org__", "~~http://127.0.0.1~~"]
)
def test_markdown_emphasis_is_not_part_of_safe_hostname(text: str) -> None:
    assert find_unsafe_urls(text) == []


@pytest.mark.parametrize(
    "text",
    [
        '"http://localhost"',
        "'https://example.org'",
    ],
)
def test_closing_quotes_are_not_part_of_safe_hostname(text: str) -> None:
    assert find_unsafe_urls(text) == []


def test_closing_bracket_separates_adjacent_urls() -> None:
    text = "[https://example.org/path]https://attacker.com/next"
    assert find_unsafe_urls(text) == ["https://attacker.com/next"]


def test_many_unmatched_closing_brackets_do_not_change_url_detection() -> None:
    text = "https://example.org/path" + ("]" * 10_000) + "https://attacker.com/end"
    assert find_unsafe_urls(text) == ["https://attacker.com/end"]


def test_embedded_scheme_starts_do_not_rescan_same_url_token() -> None:
    text = "https://example.org/" + ("https://example.org/" * 2_000)
    assert list(_iter_url_tokens(text)) == [text]
    assert find_unsafe_urls(text) == []


def test_lowercase_real_year_cve_is_detected() -> None:
    assert find_real_year_cves("see cve-2021-44228") == ["cve-2021-44228"]
    violations = validate_content_safety("see cve-2021-44228")
    assert len(violations) == 1
    assert "cve-2021-44228" in violations[0]


@pytest.mark.parametrize("value", ["CVE-2099-12345", "cve-2099-12345", "CvE-2099-12345"])
def test_fake_year_cve_is_allowed_case_insensitively(value: str) -> None:
    assert find_real_year_cves(value) == []
    assert validate_content_safety(value) == []
