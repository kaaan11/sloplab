# Independent Audit - v0.1.1 corpus, labels, provenance, and scoring

Audit performed 2026-08-25 on `main` @ `0bfb7d2` as queue item V21 of the V0.2 plan.
Scope: corpus consistency, expected-effect/expected-decision labeling, mutation
provenance, and scoring arithmetic. Findings and resolutions below.

## Checks performed and results

| Check | Method | Result |
|---|---|---|
| Corpus manifest/safety validation | `sloplab validate corpus/` | 48 fixtures, 0 errors, 0 warnings |
| Materialization drift vs committed adversarial cases | re-ran materializer on current code, byte-compared all 202 derived report/manifest files | **no drift** (lint-refactor of presentation operator is behaviorally identical) |
| Mutation seed provenance | recomputed `derive_seed(base_seed, parent_id, operator, variant_index)` for all 202 committed mutation manifests | 0 mismatches |
| Expected-decision labels | recomputed from current operator spec tables for every derived case | 0 mismatches |
| Operator category fields | compared manifest `category` against spec registry | 0 mismatches |
| Scoring arithmetic (accuracy/FAR/ORR/ECE) | independent recomputation from committed `run.jsonl` with a separate implementation | accuracy, FAR, ORR match exactly; **ECE mismatch found** (finding F-1) |

## Finding F-1: calibration bin-boundary float defect (verified, fixed)

- **Symptom:** committed ECE for rules-baseline was `0.3234`; an independent
  implementation produced `0.3134` on the identical run records.
- **Root cause:** bin bounds were computed by multiplication (`6 * 0.1` yields
  `0.6000000000000001` in IEEE-754), so confidence values sitting on decimal
  boundaries (e.g. 0.6) fell into the previous bin. On the v1-core data this moved
  69 of 250 cases between bins 5 and 6.
- **Resolution:** bounds now computed by division (`b / bins`), which is correctly
  rounded; last bin closed on the right so confidence 1.0 is always captured.
  Regression tests added in `tests/regression/test_calibration_binning.py`
  (boundary-bin placement, edge capture, hand-computed mixed-bin value).
- **Impact:** corrected ECE for rules-baseline on v1-core is `0.3134` (auxiliary
  Robustness Score moves `0.8136 -> 0.8146`). Accuracy, detection, FAR, ORR,
  robustness delta and presentation susceptibility are unaffected. Committed example
  results and the README metric table were regenerated accordingly.

## Non-findings explicitly verified

- Presentation-operator refactor (`functools.partial` substitution callback) produces
  byte-identical professionalization output to the pre-refactor lambda version.
- Oracle remains perfect across all metrics on v1-core, confirming scoring plumbing
  integrity after the fix.
- No label was adjusted anywhere in response to baseline performance (per charter).

## Disposition

All verified findings resolved on `feat/v0.2-audit-corpus` with regression coverage.
No unresolved audit findings remain.
