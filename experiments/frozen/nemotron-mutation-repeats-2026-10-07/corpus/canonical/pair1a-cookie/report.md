# DemoVault login page sets a cookie without the Secure attribute

## Summary

The demo app's login response includes a session cookie without the Secure
attribute. The sandbox is served over plain HTTP by design, so there is no TLS
transport to protect in the first place.

## Affected Component

Session middleware in DemoVault, route `POST https://demo.example.org/login`.

## Affected Versions

DemoVault 2.4.1 (demo builds only).

## Preconditions

None beyond performing a normal sign-in against the sandbox instance.

## Reproduction Steps

1. Sign in to the demo instance.
2. Inspect the Set-Cookie header of the login response.

## Observed Result

Set-Cookie includes HttpOnly and SameSite but no Secure flag.

## Expected Security Boundary

No boundary is crossed. The deployment has no HTTPS listener; marking cookies
Secure on an http-only host would break the demo's own login flow entirely.

## Impact

None in this environment. Hardening guidance for real deployments is already
covered by upstream documentation.
