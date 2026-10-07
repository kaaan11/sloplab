# Avatar upload accepts double-extension filenames in ToyTracker demo

## Summary

The avatar upload endpoint of the ToyTracker demo accepts files named with double
extensions (for example `photo.png.svg`). Whether the stored file is later served
with its original content type or the extension-implied one could not be confirmed:
the demo's storage layer rewrites names, and the mapping rule differs between the
two storage backends the bundle can use.

## Affected Component

`AvatarStore.save()` in ToyTracker profile module, route
`POST https://tracker.example.org/profile/avatar`.

## Affected Versions

ToyTracker 0.9.0 through 0.9.4 (demo builds only).

## Preconditions

- A standard demo account; avatar upload is available to all tiers.

## Reproduction Steps

1. Upload a small valid image renamed to `photo.png.svg`.
2. Note the accepted response and the returned file reference.
3. Repeat with the alternate bundled storage backend and compare references.
## Observed Result

Both uploads succeeded. Under backend A the stored name was randomized with a
`.png` suffix and served as `image/png`; under backend B the original double
extension was preserved and the file was served as `image/svg+xml`. No upload
content validation rejected either attempt.

## Expected Security Boundary

The report presumes uploads should be validated by content and served with fixed,
safe content types regardless of client-supplied names or backend choice. If the
product documents extension preservation as intended, the finding reduces to a
hardening note.

## Impact

Undetermined: potential stored-content-type confusion on backend B deployments,
conditional on undocumented serving rules. Demo avatars contain inert images.

## Notes

Both raw responses preserved in sandbox; maintainer ruling requested on the
storage abstraction contract.