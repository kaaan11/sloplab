# Release Notes - v0.1.0

First public release candidate of SlopLab, an adversarial testing framework for
vulnerability-report triage evaluators.

## What SlopLab is

A rigorous, fully offline benchmark harness answering one question:

> When a triage evaluator receives a technically valid report degraded by missing
> evidence, inflated impact, or fabricated detail, does it still classify correctly?

SlopLab is **not** a live triage product, scanner, exploit framework, web app,
RAG system, or multi-agent framework.

## Highlights

- **Corpus:** 48 hand-authored synthetic canonical fixtures (12 valid, 10 invalid,
  10 review, 8 presentation pairs as 16 files), all CC0-1.0, all validated against
  the safety policy (reserved namespaces only).
- **Mutations:** 12 deterministic operators across seven categories; byte-stable
  under fixed seeds; every derivative emits a full provenance manifest.
- **Evaluators:** normalized contract with three reference implementations -
  `oracle` (test-only ground-truth echo), `rules-baseline` (deterministic
  heuristics with documented limitations), and an optional strict-JSON LLM adapter
  (disabled by default, never invoked by tests or CI).
- **Metrics:** decision accuracy, mutation detection rate, false reassurance rate,
  over-rejection rate, robustness delta (decision drift), presentation
  susceptibility, dimension MAE, calibration error (ECE), plus an auxiliary
  weighted Robustness Score.
- **Reporting:** JSONL run logs with full provenance headers, CSV tables, and
  human-readable Markdown summaries.
- **Reproducibility:** one command rebuilds and re-evaluates the entire V1 suite;
  results are byte-identical across runs and machines (see docs/reproducibility.md).

## V1 benchmark at a glance

Suite `v1-core`: 250 evaluations (48 canonical + 202 derived). Committed reference
results in `benchmarks/results/v1-core-example/`.

| Metric (rules-baseline) | Value |
|---|---|
| Decision accuracy | 0.808 |
| Mutation detection rate | 0.766 |
| False reassurance rate | 0.126 |
| Over-rejection rate | 0.000 |
| Calibration error | 0.323 |

The oracle evaluator scores 1.0 on every metric by construction, validating the
scoring plumbing end to end.

## Commands

```bash
uv sync --group dev
uv run pytest
sloplab validate corpus/
sloplab benchmark benchmarks/suites/v1-core.yaml \
    --evaluator rules-baseline --out benchmarks/results/my-run
sloplab report benchmarks/results/my-run/run.jsonl
```

## Known limitations

See docs/methodology.md ("Known v0.1.0 baseline behaviors") and docs/final-audit.md.
Headlines: the rules baseline misses ~23% of degrading mutations; a residual false
reassurance rate on polished presentation pairs is retained deliberately as the
phenomenon under measurement; corpus is English-only.

## Compatibility

Python >= 3.11 (validated on CPython 3.14). No network access required anywhere in
the deterministic pipeline; the optional LLM adapter requires explicit user
configuration and an API key environment variable.
