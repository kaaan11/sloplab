# Download helper serves files outside the reports directory in ToyTracker

## Summary

The report-download route in ToyTracker joins a user-supplied filename onto a base
directory without canonicalization. Sequences that reference parent directories
resolve to files outside the intended reports folder.

## Affected Component

`ReportFiles.serve()` in ToyTracker reporting module, route
`GET https://tracker.example.org/reports/download?name=<file>`.

## Affected Versions

ToyTracker 0.9.0 through 0.9.4 (demo builds only).

## Preconditions

- Any signed-in demo account; downloads are available to all tiers.
- Knowledge of the demo deployment's directory layout, which is documented in its
  public README.

## Reproduction Steps

1. Sign in to the demo tracker.
2. Request `/reports/download?name=../config/demo-settings.ini`.
3. Inspect the response body and content type.

## Observed Result

The server returns the contents of the configuration file located one level above
the reports directory, with content type `application/octet-stream`.

## Expected Security Boundary

File serving must resolve names strictly within the designated reports directory,
rejecting any path that escapes it after normalization.

## Impact

Read access to sandbox configuration files as the application user. Secrets are
placeholder values by construction, limiting demonstrated impact to structure
disclosure.

An unauthenticated attacker can fully compromise the entire platform, all tenant data, and underlying infrastructure through this flaw.