# SampleStack demo allows short passwords per its bundled policy

## Summary

The demo's account creation accepts 4-character passwords because the bundled
config sets the minimum length to 4. The config file itself documents this choice.

## Affected Component

Account creation in SampleStack at `https://stack.example.org/register`.

## Affected Versions

SampleStack 3.1.0 (demo builds).

## Preconditions

None, registration is open in the sandbox.

## Reproduction Steps

1. Register with password "demo".
2. Observe success.
3. Check config/demo-auth.yaml which says min_length: 4.

## Observed Result

Weak short passwords work, matching the shipped configuration.

## Expected Security Boundary

The report suggests a longer minimum should be required. But the demo documents
this exact default and no real accounts exist; nothing is bypassed by following
the documented configuration.

## Impact

None within the sandbox. Production deployments have their own documented policy
mechanisms.
