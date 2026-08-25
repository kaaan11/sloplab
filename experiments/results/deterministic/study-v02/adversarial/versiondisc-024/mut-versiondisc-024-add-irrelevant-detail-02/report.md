# HTTP responses include a Server header with framework version in PlaygroundAPI

## Summary

HTTP responses from the PlaygroundAPI demo include a `Server` header containing
the web framework name and minor version number.

## Affected Component

HTTP server layer of PlaygroundAPI, all routes on
`https://api.example.org/`.

## Affected Versions

PlaygroundAPI 5.2.0-rc2 (demo builds only).

## Preconditions

None; any unauthenticated request exposes the header.

## Reproduction Steps

1. Send `GET /v1/status` to the demo API.
2. Inspect response headers.

## Observed Result

The response includes `Server: DemoHTTP/3.14 (sandbox)`, identifying the framework
family and minor version used by the sandbox build.

## Expected Security Boundary

The report does not identify one. Version strings in headers are a fingerprinting
convenience; the demo publishes its exact component versions in the repository's
own documentation, so the header reveals nothing that is not already public.

## Impact

None identified. Removing the header is cosmetic hardening at best. The correct
triage decision is reject.


## Additional Context

The application was originally built as a weekend project and later grew into the bundled demo. Its color scheme changed twice during development, and the mascot illustration was redrawn in 2019. The maintainers also ship a screensaver module unrelated to the web tier.
