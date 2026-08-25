# Cached response poisoning may be possible behind the demo reverse proxy in AcmePortal

## Summary

The AcmePortal demo deployment sits behind a caching reverse proxy, and some
pages reflect one unkeyed header into their cached output. Whether an external
attacker can actually poison shared cache entries depends on proxy rules that are
not exposed to tenants and were not fully observable during testing.

## Affected Component

Page rendering layer of AcmePortal behind the bundled proxy profile, route
`GET https://portal.example.org/dashboard`.

## Preconditions

- The demo started with the optional caching profile enabled.
- Knowledge of one unkeyed header name observed in proxy documentation shipped
  with the demo.

## Reproduction Steps

1. Start the demo with the caching profile.
2. Request `/dashboard` twice with differing values for the unkeyed header.
3. Compare both responses and the subsequent default (header-less) response.

## Observed Result

The first two responses differed according to the supplied header value. The
third request returned content matching the second caller's variant on two of five
runs, suggesting but not proving cache reuse of a poisoned entry. Cache logs were
not accessible from the tenant sandbox.

## Expected Security Boundary

If unkeyed input influences cached output, distinct users could receive content
shaped by another user's request; confirming this requires proxy configuration
details outside the reporter's reach.

## Impact

Potential cross-user content manipulation in deployments using the affected
profile. Undetermined without maintainer confirmation of keying rules.

## Notes

Requesting maintainer assistance to inspect the proxy keying configuration.