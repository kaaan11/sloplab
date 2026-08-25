# Bulk export may include records beyond selected filter in PlaygroundAPI

## Summary

During exploratory testing of the PlaygroundAPI demo, a bulk export request with a
tenant filter occasionally returned one or two rows that appeared to belong to
another tenant. The behavior was intermittent across repeated identical requests.

## Affected Component

`ExportJob.build_query()` in PlaygroundAPI data service, route
`POST https://api.example.org/v1/export/jobs`.

## Affected Versions

PlaygroundAPI 5.2.0-rc2 (demo builds only).

## Preconditions

- Two seeded demo tenants with overlapping record timestamps.
- An account holding the `exporter` role in tenant A.
- The export job must cross an internal pagination boundary; exact threshold is not
  documented and varied between runs (page size 100 versus 250).

## Reproduction Steps

1. Seed the demo instance using the provided multi-tenant fixture script.
2. As tenant A's exporter account, submit an export job limited to tenant A.
3. Repeat the job several times, alternating documented page sizes.
4. Diff exported rows against tenant A's dataset snapshot.

## Observed Result

Three of eleven runs produced exports containing rows whose tenant field showed
another identifier. The remaining runs matched the snapshot exactly. Logs retained
in the demo environment were rotated before they could be preserved, so no
server-side evidence accompanies this report.

## Expected Security Boundary

Exports filtered to one tenant must never include rows from another tenant,
regardless of pagination settings. If the extra rows result from a seeding artifact
rather than query logic, the finding reduces to a test-environment issue.

## Impact

If caused by query construction, this would be cross-tenant disclosure bounded by
export role membership; if caused by fixture overlap, there is no product impact.
The intermittent nature prevents confident classification without maintainer
reproduction.

## Notes

Manual review requested; happy to rerun with adjusted logging if maintainers can
extend demo log retention.
