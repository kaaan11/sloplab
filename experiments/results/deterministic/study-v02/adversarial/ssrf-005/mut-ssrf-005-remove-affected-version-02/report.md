# Import preview fetch follows internal addresses in SampleStack connector

## Summary

The connector import feature of the SampleStack demo workspace fetches a
user-supplied URL to render a preview. When the URL points at an internal loopback
address, the fetch succeeds and fragments of the internal response are embedded in
the preview payload.

## Affected Component

`ConnectorPreview.fetch()` in SampleStack integration service, route
`POST https://stack.example.org/api/connectors/preview`.

## Preconditions

- An authenticated demo workspace account; the preview feature is enabled for all
  signed-in users.
- The instance must run with its bundled local configuration in which an internal
  health service listens on the loopback interface at port 7001.

## Reproduction Steps

1. Start SampleStack with the bundled docker-compose file.
2. Sign in and open the connector import dialog.
3. Enter `http://127.0.0.1:7001/health` as the source URL and submit the preview.

## Observed Result

The dialog renders a preview containing the literal response of the internal health
service, including its build identifier and node name fields that are not exposed by
any external route. Response time confirms the request originated from the server
rather than the browser.

## Expected Security Boundary

Server-side fetches of user-supplied URLs must exclude loopback, link-local, and
private address ranges unless explicitly allow-listed, so that internal services
are unreachable from import features.

## Impact

Internal service metadata disclosure from the sandbox instance. No write primitive
was demonstrated; impact is bounded to information exposure on the local demo
deployment.