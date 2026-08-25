# GraphQL endpoint exposes full schema introspection in PlaygroundAPI demo

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The GraphQL endpoint of the PlaygroundAPI demo responds to introspection queries
With the complete schema, including internal object types and mutation argument
Documentation.

## Affected Component

GraphQL handler in PlaygroundAPI, route `POST https://api.example.org/graphql`.

## Affected Versions

PlaygroundAPI 5.2.0-rc2 (demo builds only).

## Preconditions

- Network access to the demo API; the endpoint accepts anonymous queries.

## Reproduction Steps

1. Send a standard introspection query to `/graphql`.
2. Inspect the returned schema document.

## Observed Result

The response contains the full type graph, including types prefixed with internal
Namespace markers. Whether introspection remains enabled in supported production
Configurations is not stated anywhere in the demo documentation.

## Expected Security Boundary

The report presumes schema confidentiality is intended for non-demo deployments.
If introspection is deliberately enabled for developer experience, the finding
Reduces to a configuration preference with no security boundary crossed.

## Impact

Undetermined. Schema visibility aids reconnaissance where confidential operations
Exist; the sandbox defines none, so demonstrated impact is limited to disclosure
Of structure.

## Notes

Maintainer confirmation requested regarding intended defaults outside the demo.