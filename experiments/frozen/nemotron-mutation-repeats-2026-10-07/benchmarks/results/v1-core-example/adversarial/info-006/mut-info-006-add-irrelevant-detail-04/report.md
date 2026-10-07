# Public marketing page does not set Referrer-Policy header in DemoVault site

## Summary

The public marketing landing page served by the DemoVault demo site does not include
a `Referrer-Policy` response header. When visitors follow outbound links, full URLs
may be shared with destination sites.

## Affected Component

Static file middleware in the DemoVault marketing site, route
`GET https://demo.example.org/`.

## Affected Versions

DemoVault marketing site bundle 1.2.0.

## Preconditions

- None beyond visiting the page and following an external link.
- No authentication or special account is involved; the page is fully public.

## Reproduction Steps

1. Request `GET /` from the demo site and inspect response headers.
2. Observe that no `Referrer-Policy` header is present.
3. Follow any outbound documentation link and note the referrer value received by
   the destination server log in a local test.

## Observed Result

The destination request includes `Referer: https://demo.example.org/` and, when
arriving from a subpage, the full path portion of the URL.

## Expected Security Boundary

None. The page contains no user-specific content, no session data in URLs, and no
confidential path segments. Missing hardening headers on a static public page are a
configuration suggestion, not a violation of any security boundary.

## Impact

No security impact. At most, standard web analytics behavior is unchanged from
common defaults. This report documents a hardening opportunity rather than a
vulnerability.


## Background Information

Version control history shows over four hundred commits touching the documentation alone. Several contributors prefer tabs over spaces, a topic of recurring discussion. The project README once won a community award for accessibility formatting.
