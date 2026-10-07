# Dashboard responses cached by shared proxy under rare header combinations in SampleStack

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The SampleStack demo dashboard, which renders the signed-in user's display name,
Was returned to a different test account in a small number of trials when specific
Combinations of cache-control request headers were sent. The behavior reproduced
Only twice across roughly thirty attempts, and the bundled proxy's keying rules
Were not readable from the sandbox to confirm the mechanism.

## Affected Component

Dashboard route of SampleStack behind the optional shared-cache compose profile,
Route `GET https://stack.example.org/dashboard`.

## Affected Versions

SampleStack 3.1.0 with profile `shared-cache` (demo builds only).

## Preconditions

- The demo started with the shared-cache profile (not the default).
- Two demo accounts for cross-account verification.

## Reproduction Steps

1. Start the stack with the shared-cache profile.
2. Sign in as user A and load `/dashboard`, recording response identity markers.
3. Sign in as user B and repeat while varying documented cache-control request
   Headers across attempts.
4. Compare every response against the signing-in account.

## Observed Result

In two of approximately thirty attempts, user B received a rendered page
Containing user A's display name. Both occurrences involved the same unusual
Header pair; neither occurred with default headers. Proxy logs were unavailable,
So whether a shared-cache entry or an application-side session mixup caused the
Response could not be established.

## Expected Security Boundary

Personalized pages must never be served from entries keyed without session
Context. Confirming that this boundary was crossed requires proxy configuration
Access beyond the tenant sandbox.

## Impact

If cache-keying is confirmed, personalization leakage between demo users would be
Demonstrated; the alternate explanation (session mixup in test harness) remains
Open. Severity is withheld pending mechanism confirmation.

## Notes

Proxy configuration review requested from maintainers; full attempt matrix is
Retained in the sandbox.