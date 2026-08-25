# Registration form accepts disposable email domains in SampleStack demo

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The SampleStack demo registration endpoint does not block disposable email
Domains, allowing sign-up with temporary addresses.

## Affected Component

`RegistrationBlueprint.create_account()` in SampleStack, route
`POST https://stack.example.org/register`.

## Affected Versions

SampleStack 3.1.0 (demo builds only).

## Preconditions

- Access to the public registration page of the sandbox instance.

## Reproduction Steps

1. Open the registration form on the demo instance.
2. Submit a signup using a placeholder address at `mail.example.org`.
3. Observe the confirmation response.

## Observed Result

The account is created and the flow completes normally, exactly as it would with
Any other address format the validation accepts.

## Expected Security Boundary

The report proposes that disposable addresses should be blocked. The demo's
Documented requirements specify only syntactic email validation; domain
Reputation filtering is explicitly out of scope per its design notes, and no
Other user or privilege context is affected by which address a registrant chooses.

## Impact

None identified. This is a product policy suggestion about abuse resistance, not a
Crossing of any implemented security control; reject is the appropriate decision.