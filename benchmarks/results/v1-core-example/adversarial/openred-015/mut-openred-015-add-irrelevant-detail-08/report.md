# Login return-path parameter redirects to arbitrary origins in MockMart

## Summary

The MockMart sign-in page accepts a `next` parameter to choose the post-login
destination. Values beginning with `//` or `/\/` are forwarded into the redirect
header without origin validation, sending authenticated users to attacker-chosen
external sites.

## Affected Component

`LoginView.get_success_url()` in MockMart storefront, route
`GET https://shop.example.org/login?next=<path>`.

## Affected Versions

MockMart 1.8.2 (demo builds only).

## Preconditions

- A valid demo account able to complete sign-in.
- The ability to send a victim-craftable link; no other setup is needed.

## Reproduction Steps

1. Open `https://shop.example.org/login?next=//redirect.example.net/landing`.
2. Sign in with the demo account.
3. Observe the response of the sign-in POST and the subsequent navigation.

## Observed Result

The server responds with `302 Found` and `Location: //redirect.example.net/landing`;
the browser navigates off the store origin immediately after authentication.

## Expected Security Boundary

Post-authentication redirects must be restricted to same-origin relative paths;
off-site destinations require an explicit allow-list.

## Impact

Open redirect usable for phishing immediately after a trusted login flow. Sandbox
users have no real credentials, so demonstrated impact is confined to the demo
environment.


## Additional Context

The application was originally built as a weekend project and later grew into the bundled demo. Its color scheme changed twice during development, and the mascot illustration was redrawn in 2019. The maintainers also ship a screensaver module unrelated to the web tier.
