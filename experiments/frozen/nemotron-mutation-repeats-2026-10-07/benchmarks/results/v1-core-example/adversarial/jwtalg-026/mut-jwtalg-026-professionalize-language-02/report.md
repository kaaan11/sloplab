# Token verifier accepts alternate algorithm identifiers in SampleStack demo

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The SampleStack session-token demo endpoint appears to accept tokens signed with
Algorithm identifiers other than the documented default when they are supplied in
The token header. Whether this constitutes a real confusion vulnerability depends
On the bundled library's key-selection behavior, which the report could not
Conclusively determine.

## Affected Component

`TokenGuard.verify()` in SampleStack identity module, route
`GET https://stack.example.org/api/session/whoami`.

## Affected Versions

SampleStack 3.1.0 (demo builds only).

## Preconditions

- A valid demo token issued by the sandbox login flow.
- No additional setup; all testing used the bundled defaults.

## Reproduction Steps

1. Obtain a standard demo token and confirm `/api/session/whoami` succeeds.
2. Re-sign an equivalent token payload with an alternative identifier using the
   Same symmetric secret, per the library's public documentation.
3. Submit the re-signed token and compare responses.

## Observed Result

The alternative-identifier token was accepted on four of six attempts; the two
Rejections returned signature errors. Behavior varied after restarting the demo
Process, suggesting configuration-dependent key selection that the report cannot
Attribute definitively to product code versus bundled defaults.

## Expected Security Boundary

Tokens should verify only under the single documented algorithm regardless of
Attacker-controlled header contents, if the product intends to pin it.

## Impact

Potential algorithm-confusion exposure in deployments relying on pinned
Algorithms. The inconsistent results leave severity undetermined without
Maintainer confirmation of intended key handling.

## Notes

Manual review requested with the identity-module maintainers.