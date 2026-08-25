# Documentation site allows framing of its landing page in DemoVault docs

## Summary

The public documentation landing page of the DemoVault demo site does not send
frame-ancestors restrictions, so the page can be embedded in arbitrary frames.

## Affected Component

Static hosting layer for DemoVault docs, route
`GET https://demo.example.org/docs/`.

## Affected Versions

DemoVault marketing bundle 1.2.0.

## Preconditions

None beyond a browser; the page is public and stateless.

## Reproduction Steps

1. Host a local page embedding `https://demo.example.org/docs/` in an iframe.
2. Load the local page and observe the embedded content renders without
   restriction.

## Observed Result

The docs landing page renders inside the local frame. No sensitive actions, tokens,
or account state are involved anywhere in the framed content.

## Expected Security Boundary

The report does not identify a boundary. The page exposes no user-specific or
state-changing functionality that clickjacking could leverage; framing a purely
informational page is not a violation of any documented control.

## Impact

None identified. This is a hardening suggestion for defense-in-depth, not a
vulnerability; triage should reject the report as written.
