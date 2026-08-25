# Release Notes - v0.2.0-rc1

Release candidate proving that SlopLab discriminates robustness differences between
evaluators. Scope follows decision D-0012; no new mutation operators, no runtime
product features.

## What's new

### Second deterministic evaluator
`evidence-graph-baseline` checks the minimal claim-evidence graph (impact claim ->
component support, reproduction support, boundary consistency). Label-independent by
contract, enforced by tests. Its personality is deliberately different from
rules-baseline: structure-complete reports earn trust regardless of claim quality,
which makes it an ideal contrast case.

### Comparative analysis
New `sloplab study` command plus analysis layer:
- paired win/loss comparison between evaluators,
- per-operator and per-report-class metric breakdowns,
- error taxonomy (false reassurance, premature acceptance, over-rejection, ...),
- bootstrap confidence intervals (seeded -> exactly reproducible).

### Experiment infrastructure
`experiments/` tree with versioned configs, a versioned prompt registry, run
manifests carrying full provenance (commit SHA, suite/config/prompt hashes, seed,
repeat index, request/error/timeout counters), and byte-identical record outputs
for fixed commit + corpus + seed.

### LLM pilot readiness (opt-in)
Budgeted pilot runner (`experiments/pilot.py`) enforcing request caps, timeouts and
retries from config; repeat-stability metrics; all failure modes mock-tested. Live
calls still require the `llm-bench` environment secret - adding it remains the single
manual step (see docs/llm-pilot-runbook.md).

## Corpus

Grew from 48 to **52 canonical fixtures** (12 new: 6 valid, 6 review) within the
60-fixture charter cap. Balance report: docs/corpus-balance-v0.2.md.

## Deterministic study snapshot

340 cases over both baselines (full tables in docs/evaluator-study-v0.2.md):

| Metric | rules-baseline | evidence-graph |
|---|---|---|
| Accuracy | **0.824** | 0.547 |
| Mutation detection | **0.802** | 0.000 |
| False reassurance | **0.088** | 0.438 |

The contrast demonstrates genuine discrimination between evaluator personalities -
the core V0.2 goal.

## Fixes carried into this RC

- Calibration bin-boundary float defect (audit finding F-1) with regression tests;
  ECE values corrected (docs/audit-v0.1.1.md).
- Robust path resolution for suite/corpus references from foreign working
  directories, with loud failures instead of silent empty suites.
- Baseline generality fixes (unresolved-state vocabulary, conditional boundary
  statements) - documented as corpus-adjacent calibration in the study notes.

## Known limitations

See docs/evaluator-study-v0.2.md and docs/final-audit.md. The live LLM pilot has not
been executed; its results are intentionally excluded from this RC.
