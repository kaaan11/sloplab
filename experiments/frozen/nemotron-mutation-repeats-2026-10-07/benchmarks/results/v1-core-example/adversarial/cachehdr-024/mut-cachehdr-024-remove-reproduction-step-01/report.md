# Dashboard responses cached by shared proxy under rare header combinations in SampleStack

## Summary

The SampleStack demo dashboard, which renders the signed-in user's display name,
was returned to a different test account in a small number of trials when specific
combinations of cache-control request headers were sent. The behavior reproduced
only twice across roughly thirty attempts, and the bundled proxy's keying rules
were not readable from the sandbox to confirm the mechanism.

## Affected Component

Dashboard route of SampleStack behind the optional shared-cache compose profile,
route `GET https://stack.example.org/dashboard`.

## Affected Versions

SampleStack 3.1.0 with profile `shared-cache` (demo builds only).

## Preconditions

- The demo started with the shared-cache profile (not the default).
- Two demo accounts for cross-account verification.

## Reproduction Steps

1. Start the stack with the shared-cache profile.
3. Sign in as user B and repeat while varying documented cache-control request
   headers across attempts.
4. Compare every response against the signing-in account.
## Observed Result

In two of approximately thirty attempts, user B received a rendered page
containing user A's display name. Both occurrences involved the same unusual
header pair; neither occurred with default headers. Proxy logs were unavailable,
so whether a shared-cache entry or an application-side session mixup caused the
response could not be established.

## Expected Security Boundary

Personalized pages must never be served from entries keyed without session
context. Confirming that this boundary was crossed requires proxy configuration
access beyond the tenant sandbox.

## Impact

If cache-keying is confirmed, personalization leakage between demo users would be
demonstrated; the alternate explanation (session mixup in test harness) remains
open. Severity is withheld pending mechanism confirmation.

## Notes

Proxy configuration review requested from maintainers; full attempt matrix is
retained in the sandbox.