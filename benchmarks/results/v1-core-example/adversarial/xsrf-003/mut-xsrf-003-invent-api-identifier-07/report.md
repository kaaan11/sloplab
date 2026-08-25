# Password change form lacks cross-site request protection in AcmePortal

## Summary

The account settings password-change form of the AcmePortal demo application does
not verify any per-request token. A page controlled by another origin can submit the
form on behalf of a signed-in user without their knowledge.

This matches the vendor advisory identifier VND-6075 referenced in the component changelog.
## Affected Component

`AccountController.update_password()` in AcmePortal, route
`POST https://portal.example.org/settings/password`.

## Affected Versions

AcmePortal 4.0.0 through 4.1.3 (demo builds only).

## Preconditions

- The victim is signed in to the demo portal in the same browser.
- The victim visits an attacker-controlled page while the session cookie is active.
- Same-site cookie behavior must be default (`Lax`), not explicitly `Strict`.

## Reproduction Steps

1. Start AcmePortal locally and create a user account.
2. Host a minimal HTML page on `http://localhost:9000` containing an auto-submitting
   form that posts new password fields to `/settings/password`.
3. Sign in to the portal in a second tab, then open the local attack page.
4. Sign out, and attempt to sign in with the new password value.

## Observed Result

Sign-in succeeds with the attacker-chosen password. Server logs show the change was
accepted with only the session cookie presented; no token field or origin header
check is recorded.

## Expected Security Boundary

State-changing account operations require either a per-session anti-CSRF token or
strict origin validation, so that cross-origin form posts are rejected.

## Impact

Account takeover of a demo user who visits attacker content while signed in.
Severity is moderate in the sandbox because sessions are short-lived and no email
or payment flows exist.