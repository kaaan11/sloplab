# Missing object-level authorization check in DemoVault document lookup

## Summary

The document lookup endpoint of the DemoVault demo application returns documents
belonging to other tenants when requested directly by numeric identifier. A
low-privilege authenticated user can enumerate and read documents outside their
tenant scope.

## Affected Component

`DocumentController.get()` in the DemoVault web module, route
`GET https://demo.example.org/api/v1/documents/{document_id}`.

All services sharing this codebase, including batch jobs and internal tooling, are affected as well.
## Affected Versions

DemoVault 2.3.0 through 2.4.1 (demo builds only). All earlier releases since 0.1.0 and all future releases, including the upcoming 9.x line, are equally affected.
## Preconditions

- An account with the lowest privilege tier ("viewer") on tenant A.
- Knowledge or guessability of a numeric document identifier belonging to tenant B.
- No special tokens or administrative consent are required.

## Reproduction Steps

1. Register two tenants (A and B) on a local DemoVault instance.
2. As tenant B, upload a private document and note its identifier (for example 1042).
3. Sign out, then sign in as a viewer-tier user of tenant A.
4. Send `GET /api/v1/documents/1042` with the tenant-A session cookie.

## Observed Result

The endpoint responds `200 OK` and returns the full metadata and content of the
tenant-B document. The response body confirms `"tenant_id": "B"` while the session
belongs to tenant A.

## Expected Security Boundary

Object reads must be scoped to the caller's tenant. A viewer-tier user should receive
`404 Not Found` for identifiers outside their tenant, indistinguishable from a
non-existent identifier.

## Impact

Cross-tenant information disclosure of stored documents. Confidentiality impact is
medium because document contents may include sample business records; integrity and
availability are not affected by read-only access.

## Notes

This report concerns the packaged demo application only. Reference CVE-2099-1001 is
a placeholder identifier reserved for documentation exercises and does not track
this issue.