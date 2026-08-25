# Public catalog endpoint returns wildcard CORS header in MockMart

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The anonymous product-catalog endpoint of the MockMart demo responds with
`Access-Control-Allow-Origin: *`, permitting any website to read its responses
From a visitor's browser.

## Affected Component

`CatalogBlueprint.list_products()` in MockMart, route
`GET https://shop.example.org/api/catalog`.

## Affected Versions

MockMart 1.8.2 (demo builds only).

## Preconditions

None; the endpoint requires no credentials and returns only public listing data.

## Reproduction Steps

1. Send `GET /api/catalog` with an `Origin: https://attacker.example.org` header.
   (The origin used in testing is a reserved documentation domain.)
2. Inspect the `Access-Control-Allow-Origin` response header.

## Observed Result

The response carries `Access-Control-Allow-Origin: *` and no credentials are
Involved anywhere in the flow.

## Expected Security Boundary

The report does not identify one. Wildcard CORS on an unauthenticated, public-data
Endpoint exposes nothing that any web page cannot already fetch server-side;
There is no credential-bearing cross-origin read to enable.

## Impact

None identified. The configuration choice is common for public catalogs and does
Not cross any documented boundary. Triage should reject this report.