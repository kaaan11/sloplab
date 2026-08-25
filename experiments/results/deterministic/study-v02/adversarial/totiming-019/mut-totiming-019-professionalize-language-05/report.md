# Sign-in timing differences may distinguish existing usernames in MockMart demo

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

While measuring sign-in responses for a usability task, requests for usernames that
Exist completed marginally faster on average than requests for non-existent ones.
Whether this constitutes usable username enumeration is unclear: the difference was
Small, varied between runs, and could plausibly come from database load patterns
Rather than intentional branching.

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
   Interleaved to cancel drift.
2. Record response times and compare group medians.
3. Repeat the whole procedure three times.

## Observed Result

Run A showed a median gap of about 4 ms favoring existing usernames; run B showed
About 1 ms in the same direction; run C reversed by 2 ms. Sample sizes were too
Small to separate effect from noise, and no timing source inside the application
Was available to attribute the cause.

## Expected Security Boundary

If enumeration resistance is intended, authentication must present uniform work
And timing regardless of username existence. Whether the demo claims that property
Is not documented.

## Impact

Undetermined. Even a real gap would leak only which of a handful of seeded sandbox
Usernames exists. Classification requires either many more samples or maintainer
Commentary on intended behavior.

## Notes

Raw timings are retained in the sandbox; happy to rerun with larger samples if
Maintainers want them.