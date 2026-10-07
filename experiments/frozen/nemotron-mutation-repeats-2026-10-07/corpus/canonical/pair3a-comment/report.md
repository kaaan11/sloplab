# MockMart checkout page HTML comment mentions an internal hostname

## Summary

The checkout page source contains a leftover HTML comment with a developer note
that names `build-runner.internal.example.org`, a build host.

## Affected Component

Checkout template in MockMart at `https://shop.example.org/checkout`.

## Affected Versions

MockMart 1.8.2 (demo builds).

## Preconditions

None, view-source is enough.

## Reproduction Steps

1. Open the checkout page.
2. View page source.
3. Search for "internal".

## Observed Result

One comment: `<!-- TODO: move asset pipeline off build-runner.internal.example.org -->`.

## Expected Security Boundary

The hostname belongs to reserved example.org documentation space and points to
nothing real; there's no secret material in it.

## Impact

None.
