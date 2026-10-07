# Content Security Policy relies on permissive directives in DemoVault admin demo

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The DemoVault demo's administrative pages ship a Content Security Policy that
Includes `script-src` entries permitting inline and eval-style script. Injection
Consequences therefore depend on whether the remaining headers and template
Contexts hold, which differed across the two demo profiles available for testing.

## Affected Component

Admin shell template of DemoVault, served at
`https://demo.example.org/admin/`.

## Affected Versions

DemoVault 2.4.1 (demo builds only).

## Preconditions

- One of the two bundled deployment profiles; behavior was consistent within each
  Profile but not documented as guaranteed.

## Reproduction Steps

1. Load `/admin/` under both bundled profiles and record response headers.
2. Inspect the CSP header of each.
3. Confirm which script sources each profile would allow at render time.

## Observed Result

Profile A ships `default-src 'none'; script-src 'self'`; profile B adds
`'unsafe-inline'` plus an `unsafe-eval` clause to support a bundled legacy widget.
Whether profile B is intended for exposure beyond loopback testing is not stated
Anywhere in the bundle.

## Expected Security Boundary

The report presumes strict CSP is part of the XSS defense-in-depth contract for
Admin surfaces. If profile B exists solely for offline widget development, the
Permissive directives may be acceptable by design; that intent is undocumented.

## Impact

Undetermined. In profile B, any future injection weakness gains substantially more
Room; in profile A it does not. Severity cannot be assigned without knowing which
Profile is supported for shared deployments.

## Notes

Maintainer confirmation requested on profile B's intended exposure.