# Profile update endpoint accepts privileged fields from regular users in SampleStack

## Summary

The profile-update endpoint of the SampleStack demo binds the entire JSON body to
the user model. A regular user who includes the `display_role` field in the payload
has that value persisted and rendered on their public profile, even though the web
UI never exposes it.

## Affected Component

`ProfileApi.update()` in SampleStack account service, route
`PATCH https://stack.example.org/api/profile`.

## Affected Versions

SampleStack 3.1.0 (demo builds only).

## Preconditions

- Any registered demo account; no elevated privileges required.

## Reproduction Steps

1. Sign in as a standard demo user and capture a legitimate profile update request.
2. Replay it with the JSON body extended by `"display_role": "Moderator"`.
## Observed Result

The profile header now renders "Moderator" beneath the display name. The change
persists across sessions. No actual permission change occurs; the field is purely
cosmetic state that ordinary users were never meant to control.

## Expected Security Boundary

Request binding must be restricted to fields a principal is allowed to modify;
server-assigned metadata such as role labels must ignore client-supplied values.

## Impact

Integrity issue within the demo's social surface: users can misrepresent their
standing to others. Sandbox permissions are unaffected, bounding practical impact
to demonstration value.