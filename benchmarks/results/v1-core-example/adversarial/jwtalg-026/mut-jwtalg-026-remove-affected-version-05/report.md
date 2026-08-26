# Token verifier accepts alternate algorithm identifiers in SampleStack demo

## Summary

The SampleStack session-token demo endpoint appears to accept tokens signed with
algorithm identifiers other than the documented default when they are supplied in
the token header. Whether this constitutes a real confusion vulnerability depends
on the bundled library's key-selection behavior, which the report could not
conclusively determine.

## Affected Component

`TokenGuard.verify()` in SampleStack identity module, route
`GET https://stack.example.org/api/session/whoami`.

## Preconditions

- A valid demo token issued by the sandbox login flow.
- No additional setup; all testing used the bundled defaults.

## Reproduction Steps

1. Obtain a standard demo token and confirm `/api/session/whoami` succeeds.
2. Re-sign an equivalent token payload with an alternative identifier using the
   same symmetric secret, per the library's public documentation.
3. Submit the re-signed token and compare responses.

## Observed Result

The alternative-identifier token was accepted on four of six attempts; the two
rejections returned signature errors. Behavior varied after restarting the demo
process, suggesting configuration-dependent key selection that the report cannot
attribute definitively to product code versus bundled defaults.

## Expected Security Boundary

Tokens should verify only under the single documented algorithm regardless of
attacker-controlled header contents, if the product intends to pin it.

## Impact

Potential algorithm-confusion exposure in deployments relying on pinned
algorithms. The inconsistent results leave severity undetermined without
maintainer confirmation of intended key handling.

## Notes

Manual review requested with the identity-module maintainers.