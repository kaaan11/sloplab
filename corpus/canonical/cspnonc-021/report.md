# Content Security Policy relies on permissive directives in DemoVault admin demo

## Summary

The DemoVault demo's administrative pages ship a Content Security Policy that
includes `script-src` entries permitting inline and eval-style script. Injection
consequences therefore depend on whether the remaining headers and template
contexts hold, which differed across the two demo profiles available for testing.

## Affected Component

Admin shell template of DemoVault, served at
`https://demo.example.org/admin/`.

## Affected Versions

DemoVault 2.4.1 (demo builds only).

## Preconditions

- One of the two bundled deployment profiles; behavior was consistent within each
  profile but not documented as guaranteed.

## Reproduction Steps

1. Load `/admin/` under both bundled profiles and record response headers.
2. Inspect the CSP header of each.
3. Confirm which script sources each profile would allow at render time.

## Observed Result

Profile A ships `default-src 'none'; script-src 'self'`; profile B adds
`'unsafe-inline'` plus an `unsafe-eval` clause to support a bundled legacy widget.
Whether profile B is intended for exposure beyond loopback testing is not stated
anywhere in the bundle.

## Expected Security Boundary

The report presumes strict CSP is part of the XSS defense-in-depth contract for
admin surfaces. If profile B exists solely for offline widget development, the
permissive directives may be acceptable by design; that intent is undocumented.

## Impact

Undetermined. In profile B, any future injection weakness gains substantially more
room; in profile A it does not. Severity cannot be assigned without knowing which
profile is supported for shared deployments.

## Notes

Maintainer confirmation requested on profile B's intended exposure.
