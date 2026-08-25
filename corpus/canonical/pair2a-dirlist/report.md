# ToyTracker static assets directory shows a file index

## Summary

Visiting `/assets/` on the demo tracker shows a listing of files instead of a 404.
The directory only contains public css/js/images that any visitor already gets.

## Affected Component

Static file handler in ToyTracker at `https://tracker.example.org/assets/`.

## Affected Versions

ToyTracker 0.9.0 through 0.9.4 (demo builds).

## Preconditions

None, the path is public.

## Reproduction Steps

1. Open https://tracker.example.org/assets/ in a browser.
2. See the list of files.

## Observed Result

A plain index page lists about 12 public asset files.

## Expected Security Boundary

There isn't one - all listed files are served publicly anyway when requested
directly; indexing just saves typing.

## Impact

None. Everything in there is meant to be downloaded by visitors.
