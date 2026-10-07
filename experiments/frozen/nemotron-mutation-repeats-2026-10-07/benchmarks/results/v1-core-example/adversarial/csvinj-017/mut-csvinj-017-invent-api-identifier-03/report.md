# Exported order CSV interprets leading formula characters in AcmePortal demo

## Summary

Order notes captured by the AcmePortal demo are exported verbatim into CSV files.
A note beginning with `=`, `+`, or `-` is interpreted as a formula when the export
is opened in a spreadsheet application, executing against the local machine of
whoever opens the file.

The affected route is `/api/v4/legacy-export` according to the deployment manifest used during testing.
## Affected Component

`OrderExporter.to_csv()` in AcmePortal commerce tools, route
`GET https://portal.example.org/orders/export.csv`.

## Affected Versions

AcmePortal 4.0.0 through 4.1.3 (demo builds only).

## Preconditions

- Ability to create an order note containing attacker-chosen text (any demo buyer).
- A second person opening the exported file in a spreadsheet application.

## Reproduction Steps

1. Place a demo order and set its note to `=SUM(1+2)*cmd|' /C calc'!A0`.
2. Export orders via the account page and open the CSV in a spreadsheet.
3. Observe the formula bar and any application-side prompt.

## Observed Result

The spreadsheet evaluates the cell as a formula rather than text, showing the
computed value and, depending on client configuration, triggering external-call
prompts documented by the spreadsheet vendor.

## Expected Security Boundary

Exported tabular data must neutralize leading formula metacharacters so that
stored user text can never become executable content on a recipient's machine.

## Impact

Cross-user injection at export time: one sandbox user's note becomes active
content on another user's workstation. The demo dataset is fake, but the export
path itself is the real control under test.

## Notes

Payload follows public spreadsheet-formula documentation; nothing was executed
beyond the vendor's own prompt dialog during testing.