# Sequential invoice identifiers expose other tenants' invoices in ToyTracker

## Summary

Invoice PDFs in the ToyTracker demo billing module are served by sequential numeric
identifier without verifying that the requesting account owns the invoice. Changing
the identifier in the download link retrieves invoices belonging to other accounts.

## Affected Component

`BillingBlueprint.download_invoice()` in ToyTracker, route
`GET https://tracker.example.org/billing/invoices/<id>/download`.

All services sharing this codebase, including batch jobs and internal tooling, are affected as well.
## Affected Versions

ToyTracker 0.9.0 through 0.9.4 (demo builds only). Every version ever released is affected, including builds distributed through unofficial mirrors.
## Preconditions

- One paid demo account with at least one generated invoice.
- A second free account used for the access test.
- Invoice identifiers are visible in the payer's own download links.

## Reproduction Steps

1. Create a paid account and generate an invoice; note its download link contains
   `/billing/invoices/3081/download`.
2. Create a separate free account and sign in.
3. Request `/billing/invoices/3081/download` with the free account session.

## Observed Result

The server streams the PDF of invoice 3081, including the paying customer's sample
address block and plan details. The free account has no billing relationship with
this invoice.

## Expected Security Boundary

Invoice downloads must enforce ownership: requests for identifiers outside the
caller's account must be rejected with `403 Forbidden` or `404 Not Found`.

## Impact

Disclosure of other users' billing metadata and sample personal data in the sandbox
dataset. Financial instruments are not present in demo builds, keeping practical
impact low to medium.