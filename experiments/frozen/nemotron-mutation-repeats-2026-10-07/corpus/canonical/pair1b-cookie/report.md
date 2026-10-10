# Session cookie configuration omits transport-security directive in DemoVault

## Summary

During configuration review of the DemoVault demonstration deployment, the
session-establishing response was found to omit the Secure cookie attribute. As
the sandbox exposes no TLS listener, the attribute cannot be applied without
breaking authentication; consequently no confidentiality boundary applicable to
this deployment is crossed.

## Affected Component

Session middleware in DemoVault, route `POST https://demo.example.org/login`.

## Affected Versions

DemoVault 2.4.1 (demonstration builds exclusively).

## Preconditions

Completion of a standard sign-in interaction against the sandbox instance; no
special privileges or tooling are involved.

## Reproduction Steps

1. Authenticate against the demonstration instance using valid sandbox
   credentials.
2. Examine the Set-Cookie response header issued upon successful login.
3. Record the presence and absence of individual cookie attributes.

## Observed Result

The issued cookie carries the HttpOnly and SameSite attributes while omitting
Secure, consistent with the deployment's documented HTTP-only design.

## Expected Security Boundary

The report identifies none. Transport confidentiality is not provided by this
deployment profile at any layer; accordingly, cookie transport hardening cannot
constitute a violated control here.

## Impact

None demonstrated or plausibly available within this environment. Guidance for
TLS-enabled deployments exists in upstream documentation and is unaffected.
