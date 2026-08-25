# Release Notes - v0.2.0-rc2

Patch release candidate over **v0.1.1 -> v0.2.0-rc1** line, tagged at the V26
results-audit commit.

## What changed vs v0.2.0-rc1

- **V26 results audit fix:** `evidence-graph-baseline` now breaks its
  claim-observation support edge when the report's own observation undermines the
  summary claim (`GRAPH_OBSERVED_UNDERMINES_CLAIM`), and requires a two-step
  reproduction floor for full support (`GRAPH_THIN_REPRO_SUPPORT`). This resolves
  the audit finding that the "supports" edge counted self-undermining observations.
- **Negative-control repositioning:** evidence-graph-baseline is documented in README
  and the study report as a deliberate negative control - structure-only triage,
  intentionally blind to content-quality mutations. It is not presented as a
  competitive baseline.
- Four hand-crafted mutation-family tests added (two catch, two pinned negative
  controls); progress log records the audit addendum.

## Explicitly unchanged

- No new mutation operators; operator semantics and all ground-truth labels are
  identical to rc1 (audit-verified).
- No runtime product features; live LLM pilot remains opt-in and was not executed.
- The `v0.2.0-rc1` tag/release is untouched.

## Post-fix study snapshot (340 cases)

| Metric | rules-baseline | evidence-graph (negative control) |
|---|---|---|
| Decision accuracy | **0.824** | 0.582 |
| Mutation detection | **0.802** | 0.125 |
| False reassurance | **0.088** | 0.394 |

Full analysis: docs/v26-results-audit.md and docs/evaluator-study-v0.2.md.

## Verification

156 offline tests green; ruff + mypy strict clean; deterministic study reproduces
byte-identically for this commit + seed.
