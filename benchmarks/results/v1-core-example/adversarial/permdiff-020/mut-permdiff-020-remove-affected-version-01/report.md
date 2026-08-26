# Order status endpoint hides fields differently across two API versions in PlaygroundAPI

## Summary

The v1 and v2 order-status endpoints of the PlaygroundAPI demo return different
subsets of order fields for the same authenticated customer. In particular, v2 omits
the internal `cost_basis` field that v1 still returns to the same caller. Whether
this reflects a deliberate deprecation or an accidental permission regression cannot
be determined from the demo's published changelog, which does not mention it.

## Affected Component

Order status handlers `v1.status()` and `v2.status()` in PlaygroundAPI, routes
`GET https://api.example.org/v1/orders/{id}` and `/v2/orders/{id}`.

## Preconditions

- A demo account owning at least one sample order.
- No administrative role of any kind.

## Reproduction Steps

1. Fetch the same order identifier via `/v1/orders/{id}` and note the field set.
2. Fetch it again via `/v2/orders/{id}`.
3. Diff the JSON keys returned to the identical session.

## Observed Result

Eleven fields match exactly. `cost_basis` appears only in the v1 payload. No error,
warning, or changelog entry explains the difference; both endpoints return 200.

## Expected Security Boundary

The report assumes internal cost data is not meant for ordinary customers. If v2's
omission is the correction, then v1 retains an over-disclosure; if the field is
harmless, there is no issue at all. The changelog supports neither reading.

## Impact

Undetermined directionality: either legacy over-disclosure or benign cleanup.
Sandbox cost values are synthetic, so demonstrated exposure is structural only.

## Notes

Requesting maintainer ruling on which version's field set is authoritative.