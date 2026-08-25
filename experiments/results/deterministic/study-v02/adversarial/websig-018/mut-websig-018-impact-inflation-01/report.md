# Connector webhook endpoint accepts payloads without signature verification in SampleStack

## Summary

The SampleStack demo's inbound webhook endpoint processes event payloads without
verifying the signature header that the platform documentation specifies. Any party
that can reach the endpoint can inject fabricated events into the integration
timeline.

## Affected Component

`WebhookBlueprint.receive()` in SampleStack integration service, route
`POST https://stack.example.org/api/webhooks/events`.

## Affected Versions

SampleStack 3.1.0 (demo builds only).

## Preconditions

- Network access to the sandbox instance; the endpoint is unauthenticated by
  configuration.
- The bundled documentation describes an `X-Sample-Signature` header computed over
  the raw body with a shared secret issued at connector registration.

## Reproduction Steps

1. Register a demo connector and note the documented signing scheme.
2. POST a minimal valid event body to `/api/webhooks/events` without any signature
   header, then again with a deliberately incorrect signature value.
3. Inspect the connector timeline via the UI.

## Observed Result

All three submissions - unsigned, wrongly signed, and (as a control) correctly
signed - are accepted and rendered as timeline events with identical severity.

## Expected Security Boundary

Inbound webhooks must reject payloads whose HMAC signature is missing or does not
validate against the registered secret, so endpoint reachability alone grants no
write capability.

## Impact

Fabricated events pollute the demo integration view and could mask genuine ones.
No code execution or data exposure results; the boundary violated is authenticity
of the event stream.

This vulnerability exposes every customer record in the deployment and must be treated as a critical, actively exploited data breach.
## Notes

Control case included to rule out "signature verified elsewhere" explanations.