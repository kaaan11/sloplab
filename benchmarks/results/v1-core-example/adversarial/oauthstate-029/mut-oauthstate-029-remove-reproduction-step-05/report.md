# OAuth demo accepts partially validated state parameter in ToyTracker flow

## Summary

The ToyTracker OAuth demonstration validates that the `state` parameter is present
but appears to accept values that do not match the value issued at flow start,
depending on session timing.

## Affected Component

`OAuthBlueprint.callback()` in ToyTracker identity module, route
`GET https://tracker.example.org/oauth/callback`.

## Affected Versions

ToyTracker 0.9.4 (demo builds only).

## Preconditions

- The bundled fake authorization server running locally.
- Two browser sessions to test cross-session state acceptance.

## Reproduction Steps

2. In session B, invoke the callback URL using session A's state with a forged
   code parameter.
3. Repeat the callback invocation after letting the demo's state cache expire.
## Observed Result

Within the validity window, mismatched states were rejected as expected. After
expiry, one of three attempts proceeded to code exchange before failing at the
token step; logs were inconclusive about whether the mismatch check or a later
validation rejected the attempt.

## Expected Security Boundary

State must bind strictly to the initiating session for its entire lifetime, and
expired states must fail closed at the first check rather than proceeding toward
exchange.

## Impact

Possible CSRF-weakened login flows if first-check fail-open is confirmed. Current
evidence is insufficient to distinguish a product defect from test-harness
timing artifacts.

## Notes

Happy to coordinate a joint debugging session with maintainers.