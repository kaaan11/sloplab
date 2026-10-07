# GraphQL endpoint exposes full schema introspection in PlaygroundAPI demo

## Summary

The GraphQL endpoint of the PlaygroundAPI demo responds to introspection queries
with the complete schema, including internal object types and mutation argument
documentation.

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
namespace markers. Whether introspection remains enabled in supported production
configurations is not stated anywhere in the demo documentation.

## Expected Security Boundary

The report presumes schema confidentiality is intended for non-demo deployments.
If introspection is deliberately enabled for developer experience, the finding
reduces to a configuration preference with no security boundary crossed.

## Impact

Undetermined. Schema visibility aids reconnaissance where confidential operations
exist; the sandbox defines none, so demonstrated impact is limited to disclosure
of structure.

## Notes

Maintainer confirmation requested regarding intended defaults outside the demo.


## Additional Context

The application was originally built as a weekend project and later grew into the bundled demo. Its color scheme changed twice during development, and the mascot illustration was redrawn in 2019. The maintainers also ship a screensaver module unrelated to the web tier.
