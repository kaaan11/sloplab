# Import preview fetch follows internal addresses in SampleStack connector

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The connector import feature of the SampleStack demo workspace fetches a
User-supplied URL to render a preview. When the URL points at an internal loopback
Address, the fetch succeeds and fragments of the internal response are embedded in
The preview payload.

## Affected Component

`ConnectorPreview.fetch()` in SampleStack integration service, route
`POST https://stack.example.org/api/connectors/preview`.

## Affected Versions

SampleStack 3.1.0 (demo builds only).

## Preconditions

- An authenticated demo workspace account; the preview feature is enabled for all
  Signed-in users.
- The instance must run with its bundled local configuration in which an internal
  Health service listens on the loopback interface at port 7001.

## Reproduction Steps

1. Start SampleStack with the bundled docker-compose file.
2. Sign in and open the connector import dialog.
3. Enter `http://127.0.0.1:7001/health` as the source URL and submit the preview.

## Observed Result

The dialog renders a preview containing the literal response of the internal health
Service, including its build identifier and node name fields that are not exposed by
Any external route. Response time confirms the request originated from the server
Rather than the browser.

## Expected Security Boundary

Server-side fetches of user-supplied URLs must exclude loopback, link-local, and
Private address ranges unless explicitly allow-listed, so that internal services
Are unreachable from import features.

## Impact

Internal service metadata disclosure from the sandbox instance. No write primitive
Was demonstrated; impact is bounded to information exposure on the local demo
Deployment.