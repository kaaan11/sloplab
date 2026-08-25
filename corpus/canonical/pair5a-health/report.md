# DemoVault health endpoint lists module versions publicly

## Summary

`GET /healthz` on the demo returns a JSON with every installed module and its
version. The same info is in the public changelog anyway.

## Affected Component

Health endpoint in DemoVault at `https://demo.example.org/healthz`.

## Affected Versions

DemoVault 2.4.1 (demo builds).

## Preconditions

None.

## Reproduction Steps

1. GET /healthz.
2. Read the JSON.

## Observed Result

JSON lists 6 modules with versions, matching docs/CHANGELOG.md exactly.

## Expected Security Boundary

No boundary - version info is published by the project itself.

## Impact

None.
