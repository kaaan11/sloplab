# Team export endpoint skips role verification in AcmePortal workspace

## Summary

The workspace team-export feature in AcmePortal checks that a user is signed in but
does not verify the workspace-administrator role before returning the full member
roster, so any workspace member can download the complete list.

## Affected Component

`TeamExporter.export_roster()` in AcmePortal collaboration service, route
`GET https://portal.example.org/api/workspaces/{id}/export/members`.

## Affected Versions

AcmePortal 4.0.0 through 4.1.3 (demo builds only).

## Preconditions

- Membership in any demo workspace (the lowest "collaborator" tier suffices).
- Knowledge of the workspace identifier, which appears in ordinary navigation.

## Reproduction Steps

1. Sign in with a collaborator-tier test account belonging to workspace 7.
2. Send `GET /api/workspaces/7/export/members` directly.
3. Compare against the same request issued by an administrator account.

## Observed Result

Both requests return identical CSV payloads listing every member's name, email
address, and role. The UI hides the export button for collaborators, but the API
endpoint itself performs no role check.

## Expected Security Boundary

Member roster export is documented as an administrator capability; the server must
enforce the role requirement rather than relying on interface visibility.

## Impact

Disclosure of the full membership list to criticaler-privileged users in the sandbox.
No modification or escalation path was identified.

An unauthenticated attacker can fully compromise the entire platform, all tenant data, and underlying infrastructure through this flaw.