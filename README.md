# SlopLab

**An adversarial testing framework for vulnerability-report triage evaluators.**

SlopLab measures one question:

> When a triage system receives a technically valid report that has been degraded
> with missing evidence, inflated impact, or fabricated detail, does it still
> classify the report correctly?

SlopLab is a benchmark and evaluation harness. It is **not** a live triage
product, a scanner, or an exploit framework.

## What it does

- Loads Markdown vulnerability-report fixtures with structured manifests.
- Applies controlled, traceable mutations (12 deterministic operators in V1).
- Runs pluggable evaluators through a normalized contract.
- Measures how much each mutation degrades triage decisions.
- Produces reproducible JSONL / CSV / Markdown benchmark reports.

## What it deliberately does not do

- No scanning, attacking, or interacting with real targets.
- No working exploit generation; no bug-bounty submissions.
- No "is this report true?" verdicts — only *evaluator consistency* measurement.
- No network access, API keys, or LLM required for tests or benchmarks.

See [docs/safety.md](docs/safety.md) and [docs/threat-model.md](docs/threat-model.md).

## Quick start

```bash
# install
uv sync                      # or: pip install -e .

# run the built-in V1 benchmark suite with the rules baseline evaluator
sloplab benchmark benchmarks/suites/v1-core.yaml --evaluator rules-baseline \
    --out benchmarks/results/example

# inspect results
sloplab report benchmarks/results/example/run.jsonl --format markdown
```

*(Full quick-start walkthrough with example output appears in Q12/Q14 of the build plan;
see docs/progress.md for current status.)*

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
| Mutation detection rate | Was a known degradation noticed? |
| False reassurance rate | Did the evaluator `accept` a case that should not be accepted? |
| Over-rejection rate | How often are valid reports rejected? |
| Robustness delta | How much does behavior change between canonical and mutated variants? |
| Presentation susceptibility | Does polished language buy acceptance for broken content? |
| Dimension error | Per-quality-dimension score error where expected values exist. |
| Calibration error | Do confidence values track actual correctness? |

A weighted **Robustness Score** exists only as an auxiliary summary and is
documented in [docs/methodology.md](docs/methodology.md).

## Documentation

- [Methodology](docs/methodology.md) — metric definitions and benchmark protocol
- [Threat model](docs/threat-model.md) — what SlopLab defends against, and what it is not
- [Safety policy](docs/safety.md) — content rules for fixtures and mutations
- [Evaluator contract](docs/evaluator-contract.md) — writing your own evaluator
- [Dataset card](docs/dataset-card.md) — corpus provenance and licensing
- [Reproducibility guide](docs/reproducibility.md) — seeds, hashes, run metadata
- [Decision log](docs/decision-log.md) — engineering decisions made during development
- [Progress](docs/progress.md) — build queue status

## Status

V0.1.0 release candidate. See [docs/release-notes-v0.1.0.md](docs/release-notes-v0.1.0.md).

## License

Code: MIT. Corpus fixtures: CC0-1.0 (see [docs/dataset-card.md](docs/dataset-card.md)).
