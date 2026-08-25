# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | yes |

## Reporting a vulnerability

SlopLab is an offline evaluation harness with no attack surface beyond its CLI
parsing untrusted YAML/Markdown files from the local corpus. If you find a security-
relevant issue (e.g., unsafe deserialization, path traversal in materialization, or
**sensitive/unsafe content in committed fixtures**), please report privately:

1. Open a draft security advisory via GitHub's "Security" tab, or
2. Contact the maintainers directly (see repository owner).

Please do not open public issues for sensitive findings. Include reproduction steps
and affected versions. You can expect an initial response within 7 days.

## Scope notes

- Fixture safety issues (real targets, working exploits, unlicensed material) are
  treated as security-relevant under docs/safety.md even though they are not code
  vulnerabilities.
- The optional LLM adapter makes network calls ONLY when explicitly enabled by the
  user with API configuration; this behavior is by design and documented.
