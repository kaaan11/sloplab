# Profile status field reflects input back to the same user in ToyTracker

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The profile "status message" field of the ToyTracker demo application renders its
Saved value without transformation. A user who saves a status containing markup sees
That markup applied when viewing their own profile page.

## Affected Component

`ProfileBlueprint.render_profile()` in ToyTracker, route
`GET https://tracker.example.org/profile/<own_user_id>`.

## Affected Versions

ToyTracker 0.9.0 through 0.9.4 (demo builds only).

## Preconditions

- A standard demo account.
- No second account, administrator view, or shared page is involved.

## Reproduction Steps

1. Sign in to the demo tracker and open profile settings.
2. Save a status message containing `<b>bold</b>` as the value.
3. Reload your own profile page.

## Observed Result

The word "bold" renders with bold styling on the user's own profile view.

## Expected Security Boundary

The report does not identify one. The rendered value is only ever presented to the
Same user who stored it; no other principal, privilege context, or origin receives
The content. The report explicitly confirms that other users' profile views escape
The field correctly, which removes the only plausible boundary crossing.

## Impact

No security impact. Self-only content reflection with correct escaping elsewhere is
A cosmetic observation, not a vulnerability. Triage should reject this report.