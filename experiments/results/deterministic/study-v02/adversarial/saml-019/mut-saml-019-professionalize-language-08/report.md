# SSO demo endpoint processes assertions without signature verification

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The SampleStack single sign-on demo accepts SAML responses whose digital signature
Is absent. Assertion contents, including the authenticated username, are trusted
Directly from the posted form field.

## Affected Component

`SsoBlueprint.consume_response()` in SampleStack identity module, route
`POST https://stack.example.org/sso/acs`.

## Affected Versions

SampleStack 3.1.0 (demo builds only).

## Preconditions

- The demo SSO flow enabled with its bundled self-signed metadata.
- Ability to POST a crafted response form to the assertion consumer URL; no
  Account is required beforehand.

## Reproduction Steps

1. Start the demo and note the ACS path from the bundled metadata file.
2. Post a form-encoded SAMLResponse built from the sample template with the NameID
   Set to another demo user, omitting the signature element entirely.
3. Inspect the resulting session page.

## Observed Result

The application creates an authenticated session for the NameID supplied in the
Unsigned assertion. No error or warning about the missing signature appears in
Logs.

## Expected Security Boundary

Assertions must fail closed when the enclosing Response or Assertion signature is
Missing or does not validate against the trusted metadata certificate.

## Impact

Authentication bypass within the sandbox identity domain. Because the realm is a
Demo tenant with placeholder users, real-world exposure is nil, but the control
Gap itself is unambiguous.