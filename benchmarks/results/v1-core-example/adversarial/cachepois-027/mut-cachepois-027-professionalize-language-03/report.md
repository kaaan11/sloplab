# Cached response poisoning may be possible behind the demo reverse proxy in AcmePortal

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The AcmePortal demo deployment sits behind a caching reverse proxy, and some
Pages reflect one unkeyed header into their cached output. Whether an external
Attacker can actually poison shared cache entries depends on proxy rules that are
Not exposed to tenants and were not fully observable during testing.

## Affected Component

Page rendering layer of AcmePortal behind the bundled proxy profile, route
`GET https://portal.example.org/dashboard`.

## Affected Versions

AcmePortal 4.1.3 with compose profile `proxy-cache` (demo builds only).

## Preconditions

- The demo started with the optional caching profile enabled.
- Knowledge of one unkeyed header name observed in proxy documentation shipped
  With the demo.

## Reproduction Steps

1. Start the demo with the caching profile.
2. Request `/dashboard` twice with differing values for the unkeyed header.
3. Compare both responses and the subsequent default (header-less) response.

## Observed Result

The first two responses differed according to the supplied header value. The
Third request returned content matching the second caller's variant on two of five
Runs, suggesting but not proving cache reuse of a poisoned entry. Cache logs were
Not accessible from the tenant sandbox.

## Expected Security Boundary

If unkeyed input influences cached output, distinct users could receive content
Shaped by another user's request; confirming this requires proxy configuration
Details outside the reporter's reach.

## Impact

Potential cross-user content manipulation in deployments using the affected
Profile. Undetermined without maintainer confirmation of keying rules.

## Notes

Requesting maintainer assistance to inspect the proxy keying configuration.