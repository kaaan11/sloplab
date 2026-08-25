# Stored markup injection persists through comment rendering in DemoVault

## Summary

Comments posted on shared documents in the DemoVault demo application are stored
and later rendered for every viewer of the document without output encoding,
allowing persistent markup execution in other users' browsers.

## Affected Component

`CommentView.render()` in DemoVault collaboration module, route
`GET https://demo.example.org/documents/{id}/comments`.

## Preconditions

- Two accounts sharing a demo document: an author and a viewer.
- No administrative approval is required to post comments.

## Reproduction Steps

1. As the author account, post a comment containing a sample markup payload that
   defines an image element with a non-resolving source.
2. As the viewer account, open the same document page.
3. Inspect the rendered DOM and network requests.

## Observed Result

The viewer's browser parses the injected element; the request to the non-resolving
source appears in the viewer's session context, confirming execution under the
viewer's origin.

## Expected Security Boundary

Stored user content must be encoded or sanitized at render time so that one user's
input cannot execute in another user's browsing context.

## Impact

Session-scoped content injection affecting demo viewers. The sandbox contains no
credentials worth stealing, keeping practical severity moderate.