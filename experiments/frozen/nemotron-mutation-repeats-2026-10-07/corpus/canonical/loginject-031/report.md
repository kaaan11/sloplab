# Log viewer renders submitted usernames verbatim in DemoVault admin demo

## Summary

Authentication log lines in the DemoVault admin demo store the submitted username
field as typed, and the log viewer page displays them without visible encoding.
Whether this permits markup persistence in an administrator's browser depends on
the viewer's escaping behavior, which differed between two tested browsers.

## Affected Component

`AdminLogViewer.render()` in DemoVault admin module, route
`GET https://demo.example.org/admin/logs`.

## Affected Versions

DemoVault 2.4.1 (demo builds only).

## Preconditions

- Access to the failed-login log by any means; in the sandbox the admin route is
  open for demonstration purposes (documented).
- No administrator account was used or required.

## Reproduction Steps

1. Post a failed sign-in with a username containing sample markup.
2. Open the admin log viewer page.
3. Inspect the rendered row and DOM in two different browsers.

## Observed Result

In one browser the markup rendered literally; in the other it was parsed. Source
inspection shows the value emitted identically in both cases, so the difference
appears to stem from context-specific handling that the report cannot fully
explain.

## Expected Security Boundary

If untrusted input is persisted and later displayed, it must be encoded at render
time consistently; log injection enabling script execution in reviewers' browsers
would cross a trust boundary between anonymous visitors and administrators.

## Impact

Potential stored injection against admin viewers, conditional on unresolved
rendering behavior. Severity cannot be set responsibly from current evidence.

## Notes

Manual review requested; both raw responses are preserved in the sandbox logs.
