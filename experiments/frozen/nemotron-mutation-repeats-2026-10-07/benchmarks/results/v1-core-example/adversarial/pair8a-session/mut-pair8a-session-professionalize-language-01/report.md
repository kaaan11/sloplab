# SampleStack demo session stays valid for 24 hours

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

Demo sessions last a full day per the bundled config. For a sandbox with fake
Users this does not matter.

## Affected Component

Session config in SampleStack at `https://stack.example.org/`.

## Affected Versions

SampleStack 3.1.0 (demo builds).

## Preconditions

A demo login.

## Reproduction Steps

1. Log in.
2. Read the session cookie expiry (24h).
3. Check config which says ttl_hours: 24.

## Observed Result

Exactly as configured and documented.

## Expected Security Boundary

None - it is the documented demo default, no real accounts exist.

## Impact

None.