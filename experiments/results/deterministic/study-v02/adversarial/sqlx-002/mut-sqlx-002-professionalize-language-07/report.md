# Unsanitized search filter concatenation allows query structure changes in MockMart

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The product search endpoint of the MockMart demo store builds its filter clause by
String concatenation of the `q` parameter. A crafted value changes the structure of
The generated query and returns fields from unrelated catalog rows.

## Affected Component

`search_service.build_filter()` in MockMart catalog service, route
`GET https://shop.example.org/api/search?q=<term>`.

## Affected Versions

MockMart 1.8.2; earlier 1.x demo builds are presumed affected but untested.

## Preconditions

- Network access to a local MockMart demo instance.
- No authentication is required; search is anonymous by design.

## Reproduction Steps

1. Start the MockMart demo instance with the seeded sample catalog.
2. Send `GET /api/search?q=coffee'%20OR%20'1'='1` to the local instance.
3. Compare the response with a benign query such as `GET /api/search?q=coffee`.

## Observed Result

The benign query returns 3 products. The crafted query returns 128 rows, including
Internal listing records whose `is_public` field is `false`. Error logs show the
Assembled clause with the appended condition.

## Expected Security Boundary

User-supplied terms must be treated as data, not as query syntax. Filter values
Should be passed through parameter binding so that input cannot alter the meaning
Of the statement.

## Impact

Unauthorized reading of unpublished internal catalog rows in the demo dataset.
Because the store contains only sample data, impact is limited to demonstration
Value, but the same pattern would expose private records on real datasets.