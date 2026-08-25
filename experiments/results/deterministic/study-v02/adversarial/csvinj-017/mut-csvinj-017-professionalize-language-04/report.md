# Exported order CSV interprets leading formula characters in AcmePortal demo

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

Order notes captured by the AcmePortal demo are exported verbatim into CSV files.
A note beginning with `=`, `+`, or `-` is interpreted as a formula when the export
Is opened in a spreadsheet application, executing against the local machine of
Whoever opens the file.

## Affected Component

`OrderExporter.to_csv()` in AcmePortal commerce tools, route
`GET https://portal.example.org/orders/export.csv`.

## Affected Versions

AcmePortal 4.0.0 through 4.1.3 (demo builds only).

## Preconditions

- Ability to create an order note containing attacker-chosen text (any demo buyer).
- A second person opening the exported file in a spreadsheet application.

## Reproduction Steps

1. Place a demo order and set its note to `=SUM(1+2)*cmd|' /C calc'.A0`.
2. Export orders via the account page and open the CSV in a spreadsheet.
3. Observe the formula bar and any application-side prompt.

## Observed Result

The spreadsheet evaluates the cell as a formula rather than text, showing the
Computed value and, depending on client configuration, triggering external-call
Prompts documented by the spreadsheet vendor.

## Expected Security Boundary

Exported tabular data must neutralize leading formula metacharacters so that
Stored user text can never become executable content on a recipient's machine.

## Impact

Cross-user injection at export time: one sandbox user's note becomes active
Content on another user's workstation. The demo dataset is fake, but the export
Path itself is the real control under test.

## Notes

Payload follows public spreadsheet-formula documentation; nothing was executed
Beyond the vendor's own prompt dialog during testing.