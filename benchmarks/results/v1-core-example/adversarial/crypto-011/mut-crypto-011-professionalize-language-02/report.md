# DemoVault accepts legacy cipher for internal replication channel

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The replication channel between two DemoVault demo nodes negotiated a legacy cipher
Suite during a local test, while the documented configuration intends modern
Suites only. The security consequence depends on attacker positioning and on
Whether the legacy suite remains enabled in supported builds.

## Affected Component

Replication TLS configuration in DemoVault server, service
`replication.demo.example.org:7443`.

## Affected Versions

DemoVault 2.4.1 (demo builds only).

## Preconditions

- A locally running two-node demo deployment using bundled certificates.
- A test client configured to offer legacy suites.
- Uncertain: whether packaged defaults or only the tester-provided client allow it.

## Reproduction Steps

1. Start the two-node demo deployment with the bundled compose file.
2. Probe `replication` port 7443 with a client offering both modern and legacy
   Suites, recording the negotiated suite.
3. Repeat with a modern-only client profile.

## Observed Result

The permissive probe negotiated a legacy suite; the modern-only probe negotiated a
Modern suite. Server-side configuration files were not readable from the test
Container, so the enabling party (server default versus client offer) could not be
Determined.

## Expected Security Boundary

The report assumes node-to-node traffic must never negotiate deprecated suites. If
The server merely accepted a client-offered suite that its own policy forbids, the
Finding would be invalid; if server defaults permit it, severity still hinges on
Real-world exposure of the replication port.

## Impact

Undetermined without maintainer input. Possible downgrade exposure in deployments
That expose the replication port beyond loopback; no data was decrypted and no key
Material was recovered during testing.

## Notes

Manual review requested to determine whether shipped defaults enable legacy suites.