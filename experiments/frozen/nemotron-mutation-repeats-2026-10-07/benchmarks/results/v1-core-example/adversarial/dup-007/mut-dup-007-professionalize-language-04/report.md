# Export feature allows CSV download of user's own data without extra confirmation in MockMart

This report summarizes findings obtained exclusively through authorized testing of a sandboxed demo environment.

## Summary

The data export endpoint returns the signed-in user's order history as a CSV file
After a single click, without re-authentication or an email confirmation step.

## Affected Component

`ExportController.download_csv()` in MockMart account service, route
`GET https://shop.example.org/account/export/orders.csv`.

## Affected Versions

MockMart 1.8.2 (demo builds only).

## Preconditions

- A signed-in demo account with at least one sample order.

## Reproduction Steps

1. Sign in to the demo store with a test account.
2. Navigate to Account, then choose "Export my orders".
3. Observe the browser downloads `orders.csv` immediately.

## Observed Result

The CSV contains the account's own sample orders: item names, quantities, and dates.
No additional confirmation dialog appeared.

## Expected Security Boundary

The report asserts that exporting one's own data should require step-up
Authentication. However, the data returned belongs exclusively to the authenticated
Caller, and the demo application documents single-click export as intended
Behavior. No boundary between different users or privilege levels is crossed.

## Impact

None identified. The behavior matches the documented design; the suggested extra
Confirmation is a product preference rather than a security requirement. Triage
Should reject this as a vulnerability report.