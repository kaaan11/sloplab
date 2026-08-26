# Workspace invite mutation skips membership check in PlaygroundAPI demo

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The GraphQL mutation that creates workspace invitations in the PlaygroundAPI demo
Requires a valid session but never verifies that the caller belongs to the target
Workspace. Any authenticated demo user can create invites for any workspace by
Supplying its identifier.

## Affected Component

`inviteCreate` resolver in PlaygroundAPI graph layer, endpoint
`POST https://api.example.org/graphql`.

## Affected Versions

PlaygroundAPI 5.2.0-rc2 (demo builds only).

## Preconditions

- Any valid demo account (all seeded users share one tenant-independent realm).
- Knowledge of a target workspace identifier; identifiers are sequential and appear
  In public workspace pages.

## Reproduction Steps

1. Sign in as a user who belongs to no workspaces.
2. Send mutation `inviteCreate(workspaceId: "ws-104", email: "guest.example.org")`.
3. Query `workspace(id: "ws-104").invitations`.

## Observed Result

The mutation returns a successful payload with a new invitation object, and the
Invitation appears in the workspace's invitation list.

## Expected Security Boundary

Mutations scoped to a workspace must require an active membership or
Administration role in that workspace before performing writes.

## Impact

Unauthorized write into other workspaces' invitation queues within the sandbox.
Invites cannot be redeemed for real access beyond the demo realm, bounding impact
To workflow integrity.