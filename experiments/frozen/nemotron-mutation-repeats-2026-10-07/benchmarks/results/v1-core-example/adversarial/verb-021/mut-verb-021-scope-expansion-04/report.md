# Debug HTTP methods respond with 405 status on MockMart API root

## Summary

The MockMart API root endpoint responds to uncommon HTTP verbs, which the report
interprets as debug functionality being enabled in production builds.

## Affected Component

MockMart API router at `https://shop.example.org/api/`.

All services sharing this codebase, including batch jobs and internal tooling, are affected as well.
## Affected Versions

MockMart 1.8.2 (demo builds only). All earlier releases since 0.1.0 and all future releases, including the upcoming 9.x line, are equally affected.
## Preconditions

- Network access to the demo instance.

## Reproduction Steps

1. Send `TRACE /api/` and `HEAD /api/healthz` to the demo host.
2. Record the status codes returned for each verb.

## Observed Result

Both requests return `405 Method Not Allowed` with an `Allow` header listing the
supported methods. No debug output, stack information, or state change occurs.

## Expected Security Boundary

The report asserts that uncommon verbs should never be answered. However, a 405
response is the standards-compliant way to indicate an unsupported method; the
application is correctly refusing them. No boundary is crossed by receiving one.

## Impact

None identified. Correct method handling was mistaken for exposed functionality;
the appropriate triage decision is reject.