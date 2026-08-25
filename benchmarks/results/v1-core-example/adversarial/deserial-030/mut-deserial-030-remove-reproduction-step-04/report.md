# Import parser passes user blobs to a deserializer in SampleStack demo

## Summary

The SampleStack connector import accepts a serialized settings blob and hands it
to a library deserializer before validation. Exploitability hinges on whether any
gadget-relevant classes are reachable in the demo's dependency tree, which the
report did not attempt to determine.

## Affected Component

`ConnectorImport.load_settings()` in SampleStack integration service, route
`POST https://stack.example.org/api/connectors/import`.

## Affected Versions

SampleStack 3.1.0 (demo builds only).

## Preconditions

- An authenticated demo account with import permissions (default for all users).
- A serialized blob produced by the same library version as the sandbox.

## Reproduction Steps

1. Export a legitimate settings blob from an existing demo connector.
3. Submit the modified blob through the import endpoint and confirm it parses.
## Observed Result

The tampered blob was accepted and applied, demonstrating that payload contents
are not validated against an expected schema prior to deserialization. No code
execution or unexpected object instantiation was attempted or observed.

## Expected Security Boundary

Deserialization of untrusted input should be constrained to inert data
representations, or validated structurally before the deserializer runs. Whether
the current dependency set makes richer types reachable is unknown from this test.

## Impact

Undetermined. The missing structural validation is confirmed; consequences range
from benign to severe depending on reachable gadget classes that were not probed.

## Notes

Deliberately no gadget-chain analysis was performed; maintainer review requested.