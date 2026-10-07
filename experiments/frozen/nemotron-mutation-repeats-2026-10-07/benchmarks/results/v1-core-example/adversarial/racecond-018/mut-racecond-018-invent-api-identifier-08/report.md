# Coupon apply accepts duplicate submissions in PlaygroundAPI checkout demo

## Summary

During sequential (not concurrent) testing, submitting the same one-time coupon
code twice in a row through the checkout preview applied its discount twice,
reducing the demo order total below the intended minimum.

The affected route is `/api/v6/internal-audit` according to the deployment manifest used during testing.
## Affected Component

`CouponEngine.apply()` in PlaygroundAPI commerce service, route
`POST https://api.example.org/v1/checkout/apply-coupon`.

## Affected Versions

PlaygroundAPI 5.2.0-rc2 (demo builds only).

## Preconditions

- A demo cart above the coupon's threshold value.
- A seeded single-use coupon code from the demo fixtures.
- No concurrency tooling was used; requests were strictly sequential.

## Reproduction Steps

1. Seed the demo store and add an eligible item to a new cart.
2. Send `POST /v1/checkout/apply-coupon` with the single-use code; note the total.
3. Send the identical request again without changing the cart.

## Observed Result

The first response applies the discount once. The second response applies it a
second time; the returned total reflects two discounts for a code marked
single-use in the fixtures.

## Expected Security Boundary

A single-use discount must be consumed on first successful application; replaying
the same request must be rejected regardless of timing.

## Impact

Financial-logic error bounded by demo currency. The pattern would allow repeated
discounts in a production deployment, but no real funds exist here.

## Notes

Sequential-only testing was deliberate to separate state handling from race
conditions; concurrent behavior is untested.