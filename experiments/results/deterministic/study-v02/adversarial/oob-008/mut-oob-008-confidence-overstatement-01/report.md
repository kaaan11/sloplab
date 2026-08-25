# Profile status field reflects input back to the same user in ToyTracker

## Summary

The profile "status message" field of the ToyTracker demo application renders its
saved value without transformation. A user who saves a status containing markup sees
that markup applied when viewing their own profile page.

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
same user who stored it; no other principal, privilege context, or origin receives
the content. The report explicitly confirms that other users' profile views escape
the field correctly, which removes the only plausible boundary crossing.

## Impact

No security impact. Self-only content reflection with correct escaping elsewhere is
a cosmetic observation, not a vulnerability. Triage should reject this report.
