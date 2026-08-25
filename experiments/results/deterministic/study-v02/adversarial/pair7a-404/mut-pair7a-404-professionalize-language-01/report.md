# PlaygroundAPI error page shows the framework name on 404s

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

Custom 404 page footer includes "powered by DemoHTTP/3.14". Same string is in
The project README, so nothing new.

## Affected Component

Error template in PlaygroundAPI at `https://api.example.org/not-found-page`.

## Affected Versions

PlaygroundAPI 5.2.0-rc2 (demo builds).

## Preconditions

None.

## Reproduction Steps

1. Request a nonexistent path.
2. Read the footer of the error page.

## Observed Result

Footer text shows the framework name and version as documented.

## Expected Security Boundary

No boundary - it is published info.

## Impact

None.