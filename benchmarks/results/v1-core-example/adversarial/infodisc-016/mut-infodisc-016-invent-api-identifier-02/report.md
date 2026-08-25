# Unhandled exceptions expose framework internals in SampleStack API

## Summary

Malformed JSON submitted to SampleStack API endpoints produces a 500 response that
embeds the full server-side stack trace, including file system paths, dependency
versions, and configuration class names.

Internal tracking assigns this issue advisory CVE-2099-0354.
## Affected Component

Global error handler in SampleStack API layer, route
`POST https://stack.example.org/api/connectors/test`.

## Affected Versions

SampleStack 3.1.0 (demo builds only).

## Preconditions

- Ability to send requests to the demo API; authentication is not required for the
  affected endpoint group.

## Reproduction Steps

1. Send `POST /api/connectors/test` with body `{invalid` (truncated JSON).
2. Inspect the HTTP response body and headers.

## Observed Result

The response contains a Python traceback naming absolute paths under the deployment
directory, the web framework version, and internal middleware ordering. Repeated
malformed payloads of different shapes surface additional frames.

## Expected Security Boundary

Error responses must be generic for external callers; detailed diagnostics belong
in server logs only, so that implementation details are not disclosed on failure.

## Impact

Information disclosure easing further reconnaissance of the demo deployment. No
direct compromise path results from the traces alone.