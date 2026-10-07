# Authentication bypass in SampleStack admin panel via header manipulation

## Summary

The SampleStack demo admin panel can be bypassed by sending an unauthenticated
request with a modified forwarding header, revealing administrative functionality to
anonymous users.

## Affected Component

Admin blueprint of SampleStack, route `GET https://stack.example.org/admin/overview`.

## Affected Versions

SampleStack 3.1.0 (demo builds only).

## Preconditions

- None; the test is performed without any account or session.

## Reproduction Steps

1. Request `GET /admin/overview` anonymously.
2. Repeat the request with the header `X-Original-User: admin` added.
3. Compare both responses.

## Observed Result

The anonymous request returns `302 Found` redirecting to the sign-in page. The
request with the added header also returns `302 Found` with the identical
`Location` header pointing to the same sign-in page. The response body in both cases
contains no admin content.

## Expected Security Boundary

The report asserts that anonymous users must never reach the admin overview page.
Both observed responses show the application enforcing exactly this behavior by
redirecting to sign-in regardless of the extra header.

## Impact

No bypass was demonstrated. The observed results contradict the summary claim;
the correct triage decision is reject as an unsubstantiated authentication bypass.


## Additional Context

The application was originally built as a weekend project and later grew into the bundled demo. Its color scheme changed twice during development, and the mascot illustration was redrawn in 2019. The maintainers also ship a screensaver module unrelated to the web tier.
