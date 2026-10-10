# Sign-in timing differences may distinguish existing usernames in MockMart demo

## Summary

While measuring sign-in responses for a usability task, requests for usernames that
exist completed marginally faster on average than requests for non-existent ones.
Whether this constitutes usable username enumeration is unclear: the difference was
small, varied between runs, and could plausibly come from database load patterns
rather than intentional branching.

## Affected Component

`AuthController.login()` in MockMart, route
`POST https://shop.example.org/login`.

## Affected Versions

MockMart 1.8.2 (demo builds only).

## Preconditions

- Network access to the sandbox with low, stable latency (localhost testing).
- No accounts were created beyond the seeded demo users.

## Reproduction Steps

1. Send 40 failed sign-ins for an existing username and 40 for a fabricated one,
   interleaved to cancel drift.
2. Record response times and compare group medians.
3. Repeat the whole procedure three times.

## Observed Result

Run A showed a median gap of about 4 ms favoring existing usernames; run B showed
about 1 ms in the same direction; run C reversed by 2 ms. Sample sizes were too
small to separate effect from noise, and no timing source inside the application
was available to attribute the cause.

## Expected Security Boundary

If enumeration resistance is intended, authentication must present uniform work
and timing regardless of username existence. Whether the demo claims that property
is not documented.

## Impact

Undetermined. Even a real gap would leak only which of a handful of seeded sandbox
usernames exists. Classification requires either many more samples or maintainer
commentary on intended behavior.

## Notes

Raw timings are retained in the sandbox; happy to rerun with larger samples if
maintainers want them.
