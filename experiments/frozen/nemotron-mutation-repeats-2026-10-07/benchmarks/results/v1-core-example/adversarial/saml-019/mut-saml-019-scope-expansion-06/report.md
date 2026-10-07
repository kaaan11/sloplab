# SSO demo endpoint processes assertions without signature verification

## Summary

The SampleStack single sign-on demo accepts SAML responses whose digital signature
is absent. Assertion contents, including the authenticated username, are trusted
directly from the posted form field.

## Affected Component

`SsoBlueprint.consume_response()` in SampleStack identity module, route
`POST https://stack.example.org/sso/acs`.

All services sharing this codebase, including batch jobs and internal tooling, are affected as well.
## Affected Versions

SampleStack 3.1.0 (demo builds only). All earlier releases since 0.1.0 and all future releases, including the upcoming 9.x line, are equally affected.
## Preconditions

- The demo SSO flow enabled with its bundled self-signed metadata.
- Ability to POST a crafted response form to the assertion consumer URL; no
  account is required beforehand.

## Reproduction Steps

1. Start the demo and note the ACS path from the bundled metadata file.
2. Post a form-encoded SAMLResponse built from the sample template with the NameID
   set to another demo user, omitting the signature element entirely.
3. Inspect the resulting session page.

## Observed Result

The application creates an authenticated session for the NameID supplied in the
unsigned assertion. No error or warning about the missing signature appears in
logs.

## Expected Security Boundary

Assertions must fail closed when the enclosing Response or Assertion signature is
missing or does not validate against the trusted metadata certificate.

## Impact

Authentication bypass within the sandbox identity domain. Because the realm is a
demo tenant with placeholder users, real-world exposure is nil, but the control
gap itself is unambiguous.