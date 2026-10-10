# Dashboard websocket drops reconnects with expired tokens in AcmePortal demo

## Summary

The AcmePortal demo dashboard opens a websocket authenticated by a short-lived
token in the query string. During testing, connections established near token
expiry behaved inconsistently: some were accepted and stayed open past expiry,
while identical attempts at other moments were rejected outright. The intended
expiry semantics for already-established sockets are not documented.

## Affected Component

`DashboardSocket.on_connect()` in AcmePortal realtime module, route
`wss://portal.example.org/ws/dashboard?token=<jwt>`.

## Affected Versions

AcmePortal 4.1.3 (demo builds only).

## Preconditions

- A signed-in demo user; dashboard page open.
- Timing coordinated against the bundled 60-second demo token lifetime.

## Reproduction Steps

1. Open the dashboard and note the websocket URL's token parameter.
2. Initiate socket connections at 5, 30, 55, and 59 seconds of token life.
3. For accepted sockets, keep them open and record whether the server closes them
   when the embedded token expires.

## Observed Result

Connections at 5 s and 30 s always succeeded; 55 s succeeded twice out of four
attempts; 59 s never succeeded. Of the sockets opened before expiry, three stayed
open indefinitely and one was closed by the server after roughly 40 additional
seconds, without any documented policy explaining either behavior.

## Expected Security Boundary

The report presumes long-lived sockets should re-authenticate or be closed at token
expiry. If the product instead binds authorization to connection time only, the
observed acceptance is correct and no boundary is crossed.

## Impact

Undetermined. Inconsistent enforcement could allow stale-credential message
streams in deployments relying on expiry as a control; sandbox dashboards carry no
sensitive data.

## Notes

Maintainer clarification on intended socket lifetime semantics requested.
