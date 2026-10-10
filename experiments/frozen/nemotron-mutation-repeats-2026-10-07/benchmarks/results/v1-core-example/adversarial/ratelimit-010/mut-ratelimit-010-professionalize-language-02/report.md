# Login endpoint permits high request rates from a single source in AcmePortal

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The sign-in endpoint of the AcmePortal demo application accepted repeated failed
Login attempts at a sustained rate during testing, suggesting that rate limiting may
Be absent or misconfigured for some deployment modes.

## Affected Component

`AuthController.login()` in AcmePortal, route
`POST https://portal.example.org/login`.

## Affected Versions

AcmePortal 4.1.3 (demo builds only); other versions untested.

## Preconditions

- Network access to a demo instance started with the default compose profile.
- Behavior is expected to differ when the optional `RATE_LIMIT_BACKEND` service is
  Configured; the tested instance ran without it.

## Reproduction Steps

1. Start AcmePortal with the default compose profile (no rate-limit backend).
2. Send 60 consecutive `POST /login` requests with an incorrect password for one
   Test account over two minutes.
3. Record the status codes and any `Retry-After` headers returned.

## Observed Result

All 60 attempts returned `401 Unauthorized` with no throttling signals. Two of the
Attempts returned `500 Internal Server Error` before recovering. Whether a real
Deployment would behave identically depends on the reverse proxy and backend
Configuration, which were not available in this environment.

## Expected Security Boundary

Authentication endpoints should constrain guessing through per-source throttling or
Equivalent controls in production profiles. It is not clear whether the observed
Behavior reflects a product defect or the intentionally minimal default profile.

## Impact

Potentially easier password guessing against deployments lacking the optional
Backend. Deployment-context dependence leaves both likelihood and severity
Undetermined without maintainer confirmation.

## Notes

Manual review requested: maintainers should confirm whether production profiles
Enable throttling by default.