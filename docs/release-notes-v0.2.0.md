# Release Notes - v0.2.0

Comparative evaluator study release. **V0.2 closes as a deterministic-scope
release: the live LLM experiment was not executed.** The strict-JSON adapter, its
mock-based failure tests, and the full experiment/reproducibility infrastructure
ship complete; running the pilot later requires only the `llm-bench` environment
secret (deferred to backlog - see docs/llm-pilot-runbook.md).

## Headline

The framework now demonstrably discriminates robustness differences between
evaluators. On the 52-fixture corpus (340 cases, seed `20260825`):

| Metric | rules-baseline | evidence-graph-baseline |
|---|---|---|
| Decision accuracy | **0.824** | 0.582 |
| Mutation detection rate | **0.802** | 0.125 |
| False reassurance rate | **0.088** | 0.394 |

The evidence-graph baseline is published as a deliberate **negative control**:
structure-only triage that is blind to content-quality mutations. Its profile -
and the paired win/loss gap above - is the measurement this release exists to
deliver. Analysis: docs/evaluator-study-v0.2.md, docs/v26-results-audit.md.

## Since v0.1.1

- **Independent audit** of corpus/labels/provenance/scoring with one verified fix:
  calibration bin-boundary float defect corrected + regression tests
  (docs/audit-v0.1.1.md).
- **Corpus:** 12 new synthetic fixtures (6 valid, 6 review) -> 52 total, balance
  report committed (docs/corpus-balance-v0.2.md).
- **New evaluator:** evidence-graph-baseline (negative control), label-independent,
  contract-conformance tested.
- **Experiment infrastructure:** versioned configs, prompt registry, run manifests
  with full provenance, byte-identical study runner (`sloplab study`).
- **Comparative analysis:** paired win/loss, per-operator/per-class breakdowns,
  error taxonomy, seeded bootstrap confidence intervals.
- **LLM pilot readiness:** budgeted runner with request/timeout/retry caps and
  repeat-stability metrics; every failure mode mock-tested; zero live calls.
- **Docs:** evaluator study guide, LLM pilot runbook, reproducibility update,
  V26 audit and corpus balance reports.
- **Fixes:** robust suite/corpus path resolution from foreign working directories;
  calibration binning defect; baseline generality improvements (documented as
  corpus-adjacent calibration).

## Verification

156 offline tests green on a clean environment install; ruff + mypy strict clean;
deterministic study reproduces byte-identically from a foreign working directory.

## Pre-releases

`v0.2.0-rc1` and `v0.2.0-rc2` remain published as pre-releases, untouched.

## Deferred

Live LLM pilot -> docs/backlog.md (future opt-in study). No timeline commitment.
