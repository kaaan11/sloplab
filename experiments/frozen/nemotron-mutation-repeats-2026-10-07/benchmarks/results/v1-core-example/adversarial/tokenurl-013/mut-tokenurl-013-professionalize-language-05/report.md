# Session token echoed in redirect query parameter in MockMart checkout

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

After completing guest checkout, the MockMart demo app appends the session token to
The success-redirect URL as a query parameter. The token therefore lands in places
That routinely log URLs: browser history, and any intermediary that records full
Request lines.

## Affected Component

`CheckoutController.finish()` in MockMart storefront, route
`GET https://shop.example.org/checkout/done`.

## Affected Versions

MockMart 1.8.2 (demo builds only).

## Preconditions

- Completion of a standard guest checkout in the sandbox store.
- No special tooling; the value is visible in the browser address bar.

## Reproduction Steps

1. Add any sample item to the cart and complete guest checkout.
2. Observe the final redirect destination in the address bar.
3. Copy the URL and inspect its query parameters.

## Observed Result

The URL contains `?session=<token>` where `<token>` matches the value of the
Session cookie issued during the flow.

## Expected Security Boundary

Session credentials must travel only in protected channels (cookies with proper
Attributes), never in URLs, because URLs are commonly logged and shared.

## Impact

Exposure of a live session credential to URL-logging surfaces within the sandbox.
The demo holds no real accounts, keeping demonstrated impact contained to control
Quality rather than concrete compromise.