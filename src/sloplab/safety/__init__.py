"""Safety policy helpers for synthetic identifier namespaces."""

from sloplab.safety.policy import (
    FAKE_CVE_YEAR,
    RESERVED_DOMAINS,
    SYNTHETIC_PERSONS,
    SYNTHETIC_PRODUCTS,
    find_real_year_cves,
    find_unsafe_urls,
    is_reserved_host,
    validate_content_safety,
)

__all__ = [
    "FAKE_CVE_YEAR",
    "RESERVED_DOMAINS",
    "SYNTHETIC_PERSONS",
    "SYNTHETIC_PRODUCTS",
    "find_real_year_cves",
    "find_unsafe_urls",
    "is_reserved_host",
    "validate_content_safety",
]
