# Connector webhook endpoint accepts payloads without signature verification in SampleStack

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The SampleStack demo's inbound webhook endpoint processes event payloads without
Verifying the signature header that the platform documentation specifies. Any party
That can reach the endpoint can inject fabricated events into the integration
Timeline.

## Affected Component

`WebhookBlueprint.receive()` in SampleStack integration service, route
`POST https://stack.example.org/api/webhooks/events`.

## Affected Versions

SampleStack 3.1.0 (demo builds only).

## Preconditions

- Network access to the sandbox instance; the endpoint is unauthenticated by
  Configuration.
- The bundled documentation describes an `X-Sample-Signature` header computed over
  The raw body with a shared secret issued at connector registration.

## Reproduction Steps

1. Register a demo connector and note the documented signing scheme.
2. POST a minimal valid event body to `/api/webhooks/events` without any signature
   Header, then again with a deliberately incorrect signature value.
3. Inspect the connector timeline via the UI.

## Observed Result

All three submissions - unsigned, wrongly signed, and (as a control) correctly
Signed - are accepted and rendered as timeline events with identical severity.

## Expected Security Boundary

Inbound webhooks must reject payloads whose HMAC signature is missing or does not
Validate against the registered secret, so endpoint reachability alone grants no
Write capability.

## Impact

Fabricated events pollute the demo integration view and could mask genuine ones.
No code execution or data exposure results; the boundary violated is authenticity
Of the event stream.

## Notes

Control case included to rule out "signature verified elsewhere" explanations.