# Debug HTTP methods respond with 405 status on MockMart API root

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The MockMart API root endpoint responds to uncommon HTTP verbs, which the report
Interprets as debug functionality being enabled in production builds.

## Affected Component

MockMart API router at `https://shop.example.org/api/`.

## Affected Versions

MockMart 1.8.2 (demo builds only).

## Preconditions

- Network access to the demo instance.

## Reproduction Steps

1. Send `TRACE /api/` and `HEAD /api/healthz` to the demo host.
2. Record the status codes returned for each verb.

## Observed Result

Both requests return `405 Method Not Allowed` with an `Allow` header listing the
Supported methods. No debug output, stack information, or state change occurs.

## Expected Security Boundary

The report asserts that uncommon verbs should never be answered. However, a 405
Response is the standards-compliant way to indicate an unsupported method; the
Application is correctly refusing them. No boundary is crossed by receiving one.

## Impact

None identified. Correct method handling was mistaken for exposed functionality;
The appropriate triage decision is reject.