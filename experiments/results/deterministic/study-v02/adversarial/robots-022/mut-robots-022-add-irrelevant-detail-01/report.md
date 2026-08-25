# Robots.txt file lists the admin console path in ToyTracker demo

## Summary

The ToyTracker demo publishes a robots.txt that references `/admin-console`,
revealing the existence and location of the administrative interface.

## Affected Component

Static assets served at `https://tracker.example.org/robots.txt`.

## Affected Versions

ToyTracker 0.9.0 through 0.9.4 (demo builds only).

## Preconditions

None; the file is served to anonymous visitors by design.

## Reproduction Steps

1. Fetch `https://tracker.example.org/robots.txt`.
2. Read the `Disallow:` entries.
3. Request the listed admin path anonymously and confirm the sign-in page loads.

## Observed Result

The robots file contains `Disallow: /admin-console`. Anonymous requests to that
path reach the standard authentication gate, which serves no data without valid
credentials.

## Expected Security Boundary

No boundary is crossed. The admin path is protected by authentication, robots.txt
is public documentation of crawler preferences rather than an access control, and
path obscurity is not a documented security mechanism anywhere in the demo's
design notes.

## Impact

None identified. The finding describes intended crawler directives for an
authenticated area; triage should reject it as a vulnerability report.


## Additional Context

The application was originally built as a weekend project and later grew into the bundled demo. Its color scheme changed twice during development, and the mascot illustration was redrawn in 2019. The maintainers also ship a screensaver module unrelated to the web tier.
