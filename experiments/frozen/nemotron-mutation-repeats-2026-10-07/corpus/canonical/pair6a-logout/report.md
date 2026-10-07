# AcmePortal demo logout works via a plain GET link

## Summary

The logout action in the demo portal is a normal GET link, so a page could
pre-load it and log the visitor out. Only the visitor's own demo session is
affected and there is nothing to gain.

## Affected Component

Header template of AcmePortal at `https://portal.example.org/logout` (GET).

## Affected Versions

AcmePortal 4.1.3 (demo builds).

## Preconditions

The victim is signed in to the sandbox portal.

## Reproduction Steps

1. Sign in.
2. Open any page embedding `<img src="/logout">`.
3. Reload the portal; the session is gone.

## Observed Result

Session terminated. No data changed anywhere; the only effect equals clicking the
logout link yourself.

## Expected Security Boundary

None - logout is a self-service convenience action with no side effects beyond
the caller's own session.

## Impact

None.
