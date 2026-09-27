# SlopLab

[![CI](https://github.com/kaaan11/sloplab/actions/workflows/ci.yml/badge.svg)](https://github.com/kaaan11/sloplab/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/kaaan11/sloplab)](https://github.com/kaaan11/sloplab/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Corpus: CC0-1.0](https://img.shields.io/badge/corpus-CC0--1.0-lightgrey.svg)](docs/dataset-card.md)
![Python](https://img.shields.io/badge/python-3.11%2B-informational)

**An adversarial testing framework for vulnerability-report triage evaluators.**

SlopLab measures one question:

> When a triage system receives a technically valid report that has been degraded
> with missing evidence, inflated impact, or fabricated detail, does it still
> classify the report correctly?

SlopLab is a benchmark and evaluation harness. It is **not** a live triage product,
a scanner, or an exploit framework.

**Current release: [v0.2.2](https://github.com/kaaan11/sloplab/releases/tag/v0.2.2)**
([release notes](docs/release-notes-v0.2.2.md)).

## What it does

- Loads Markdown vulnerability-report fixtures with structured manifests.
- Applies controlled, traceable mutations (12 deterministic operators in V1).
- Runs pluggable evaluators through a normalized contract.
- Measures how much each mutation degrades triage decisions.
- Produces reproducible JSONL / CSV / Markdown / offline HTML benchmark reports.

## What it deliberately does not do

- No scanning, attacking, or interacting with real targets.
- No working exploit generation; no bug-bounty submissions.
- No "is this report true?" verdicts — only *evaluator consistency* measurement.
- No network access, API keys, or LLM required for tests or benchmarks.

See [docs/safety.md](docs/safety.md) and [docs/threat-model.md](docs/threat-model.md).

## Quick start

```bash
git clone <repo-url> && cd sloplab
uv sync --group dev          # or: pip install -e .

# validate the committed corpus (60 fixture files / 52 logical reports)
sloplab validate corpus/

# run the full V1 benchmark with the deterministic rules baseline (~297 cases)
sloplab benchmark benchmarks/suites/v1-core.yaml \
    --evaluator rules-baseline --out benchmarks/results/my-run

# human-readable metrics summary
sloplab report benchmarks/results/my-run/run.jsonl
```

`sloplab benchmark` writes a plain result directory without a completion marker, so
`report`/`compare` print `note: ... is a legacy bundle without integrity guarantees`.
That note is expected here. Integrity-marked bundles (completion marker and hash
verification) are written by `sloplab study` and the LLM pilot.

Bring your own **trusted local Python evaluator**, alongside the baseline, without
editing SlopLab source. See the [five-minute BYOE guide](docs/bring-your-own-evaluator.md).

```bash
uv run sloplab benchmark benchmarks/suites/v1-core.yaml --evaluator rules-baseline --evaluator-module examples/my_evaluator.py:make --out /tmp/byoe
uv run sloplab report /tmp/byoe/run.jsonl --format html --out /tmp/byoe/report.html
```

## Optional Report Builder

```bash
uv sync --extra ui
uv run sloplab add-report path/to/synthetic-report.md --ui
```

The keyboard-first terminal builder guides source, ground truth, evidence,
quality scores and review through the same validated transaction as the classic
CLI. No UI dependency is required for `sloplab add-report report.md` without
`--ui`. See the [Report Builder guide](docs/report-builder.md) for controls,
installation and cleanup-warning semantics.

## Evaluators

| Evaluator | Role | Notes |
|---|---|---|
| `rules-baseline` | **in-domain reference** | deterministic lexical heuristics tuned on this corpus; the floor to beat in-domain, not a general triage claim |
| `evidence-graph-baseline` | **negative control** | structure-only claim-evidence graph; intentionally blind to content-quality mutations - it exists to prove the benchmark detects such blindness, not to win |
| `oracle` | test-only | echoes ground truth; validates scoring plumbing |
| `llm-json` | opt-in live adapter | disabled by default; see pilot runbook |

A step-by-step walkthrough with real output lives in
[examples/walkthrough.md](examples/walkthrough.md). Reference results regenerated at
v0.2.2 live in [benchmarks/results/v1-core-example/](benchmarks/results/v1-core-example/)
(oracle + rules-baseline; the documented reproduction command in
[docs/reproducibility.md](docs/reproducibility.md) reproduces them exactly).

Example v1-core numbers (rules-baseline, regenerated for PR #33 fixing issue
#20; see methodology.md for definitions). **What these numbers are:** agreement
with the authored target decisions of this synthetic, single-author collection
(60 fixtures representing 52 logical reports, 297 realized cases). They are
*not* validated triage accuracy, bug-bounty performance, or general evaluator
robustness; no independent human validation of the targets has been completed.
The rules baseline was developed against this very corpus: the PR #33 accuracy
gain (0.811 -> 0.848 from 11 conditional-boundary corrections) is in-domain
target agreement, not generalization evidence. An ablation study
(post-hoc, exploratory) found that most of the baseline's
decision-changing-target hits depend on regex patterns that share literal text
with the mutation operators' templates; see [Threat model](docs/threat-model.md).

| metric | value |
|---|---|
| decision accuracy | 0.848 |
| decision-changing target accuracy (formerly "mutation detection rate") | 0.802 |
| false reassurance rate | 0.094 |
| over-rejection rate | 0.000 |
| calibration error | 0.339 |

**Uncertainty (95% accuracy intervals, primary = logical-report cluster bootstrap).**
Estimand: *within this fixed synthetic collection, treating logical-report clusters
as exchangeable resampling units*. The interval is a sensitivity analysis inside
this corpus; it is not external validity for real-world reports. Row-level
case resampling is shown only for comparison (it understates dependence between
derived cases).

| | row-level case bootstrap (old) | cluster bootstrap, 52 logical reports (primary) |
|---|---|---|
| rules-baseline | [0.805, 0.889] | **[0.7857, 0.9020]** |
| evidence-graph-baseline (negative control) | [0.485, 0.596] | **[0.4581, 0.6300]** |
| paired difference, same resample (rules-baseline minus evidence-graph-baseline) | — | **[0.2027, 0.4000]**, point 0.3050 |

> Caveat: **52 clusters is a cluster count, not an effective sample size.**
> Shared authorship and report templates also create dependence *between*
> clusters, so the wider cluster intervals are a lower bound on real-world
> uncertainty, not a full accounting.

## Architecture

```text
        canonical fixtures ──► mutation planner ──► mutation operators
                                                        │
                                        mutated report + provenance manifest
                                                        │
                     ┌──────────────────────────────────┼──────────────────┐
                     ▼                                  ▼                  ▼
              rules evaluator                    oracle evaluator     llm adapter (opt.)
                     └──────────────────────────────────┼──────────────────┘
                                                        ▼
                                       normalized evaluation result (JSON)
                                                        ▼
                                            metrics & aggregation
                                                        ▼
                                         JSONL / CSV / Markdown reports
```

Design principle: the corpus, mutation engine, evaluator, and metrics layers are
independent. Adding an evaluator never requires changing fixtures or mutations.

## Metrics

SlopLab intentionally avoids a single "accuracy" number as the headline result.
Primary metrics are reported per dimension:

| Metric | Question it answers |
|---|---|
| Decision accuracy | Does the decision match ground truth? |
| Decision-changing target accuracy | Of derived cases whose expected decision is designed to change the parent-class decision, how often does the evaluator match the changed decision? |
| False reassurance rate | Did the evaluator `accept` a case that should not be accepted? |
| Over-rejection rate | How often are valid reports rejected? |
| Decision-preserving drift | On decision-preserving mutations, how often does the evaluator's decision differ from its canonical-parent decision? |
| Presentation susceptibility | Acceptance gained by polished-but-broken variants over their canonical parents (operator-generated presentation mutations only). |
| Dimension error | Per-quality-dimension score error where expected values exist. |
| Calibration error | Do confidence values track actual correctness? |

A weighted **Robustness Score** exists only as an auxiliary summary and is
documented in [docs/methodology.md](docs/methodology.md). It must not be used
for ranking: a blind always-`needs_manual_review` policy scores 0.740 on it
(rules-baseline 0.839); the same blind policy reaches 0.760 decision-changing
target accuracy with zero false reassurance. Reproduce with:
`uv run python scripts/blind_policy_compare.py` (#45).

Old metric names ("mutation detection rate", "quality-neutral mutations",
"robustness delta") and their replacements are mapped in
[docs/terminology-changes.md](docs/terminology-changes.md).

## Documentation

- [Methodology](docs/methodology.md) — metric definitions and benchmark protocol
- [Terminology changes](docs/terminology-changes.md) — old metric names → new names, and why (#44–#52)
- [Evaluator study guide](docs/evaluator-study.md) — run and read comparative studies
- [LLM pilot runbook](docs/llm-pilot-runbook.md) — the only manual, metered step
- [Threat model](docs/threat-model.md) — what SlopLab defends against, and what it is not
- [Safety policy](docs/safety.md) — content rules for fixtures and mutations
- [Evaluator contract](docs/evaluator-contract.md) — writing your own evaluator
- [Dataset card](docs/dataset-card.md) — corpus provenance and licensing
- [Reproducibility guide](docs/reproducibility.md) — seeds, hashes, run metadata
- [Decision log](docs/decision-log.md) — engineering decisions made during development
- [Progress](docs/progress.md) — build queue status

## Status

v0.2.2 - audit-remediation patch over the v0.2.x
deterministic-scope releases: no-op derived cases eliminated, mutation/provenance
and identity-hygiene fixes, safety enforcement tests, documentation regeneration.
Live LLM pilot remains deferred; see
[docs/remediation-audit-v0.2.2.md](docs/remediation-audit-v0.2.2.md) and
[docs/release-notes-v0.2.2.md](docs/release-notes-v0.2.2.md).

## License

Code: MIT. Corpus fixtures: CC0-1.0 (see [docs/dataset-card.md](docs/dataset-card.md)).
