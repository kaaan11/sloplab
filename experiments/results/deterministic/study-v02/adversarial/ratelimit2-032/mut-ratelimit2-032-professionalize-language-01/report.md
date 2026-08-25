# Metered API allows quota counter reset under unclear conditions in PlaygroundAPI

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

While testing the PlaygroundAPI demo's rate metering, the quota counter for a test
Tenant occasionally reset to its full allowance without any documented trigger.
The resets did not correlate obviously with request volume, restarts, or elapsed
Wall-clock time.

## Affected Component

`QuotaLedger.consume()` in PlaygroundAPI metering service, route
`GET https://api.example.org/v1/usage`.

## Affected Versions

PlaygroundAPI 5.2.0-rc2 (demo builds only).

## Preconditions

- A demo tenant with the standard seeded quota.
- No special privileges; usage endpoints are tenant-readable.

## Reproduction Steps

1. Note the initial quota via `/v1/usage`.
2. Issue metered requests until roughly half the allowance is consumed.
3. Poll `/v1/usage` at varied intervals, recording counter values and timestamps.
4. Repeat across two sandbox restart cycles.

## Observed Result

Across nine observation windows, the counter returned to full allowance three
Times: once after a restart, once mid-run with no restart, and once after a long
Idle gap. The remaining six windows behaved as expected. Demo logs rotate too
Quickly to capture the ledger's internal events.

## Expected Security Boundary

If quota is a security-relevant limit rather than a billing convenience,
Undocumented resets could undermine abuse controls; if it is best-effort
Metering, no boundary applies. The product documentation does not say which.

## Impact

Undetermined pending clarification of intended semantics. Demonstrated variance
Affects only demo counters.

## Notes

Maintainer input requested on whether the ledger carries durability guarantees.