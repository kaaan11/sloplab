# Evaluator Study Guide (v0.2)

How to run and interpret the deterministic evaluator comparison.

## Run it

```bash
uv sync --group dev
uv run sloplab study experiments/configs/deterministic-study-v0.2.yaml \
    --out experiments/results/deterministic/study-v02
```

Outputs in the target directory:

| File | Contents |
|---|---|
| `records.jsonl` | one normalized evaluation record per case per evaluator |
| `manifest.json` | provenance: commit SHA, suite hash, config hash, seed, times |
| `analysis.json` | bundles, paired comparisons, error taxonomy, bootstrap CIs |
| `report.md` | human-readable summary |
| `results.csv` | flat per-case table |

Byte-identity contract: for a fixed commit + corpus + seed, `records.jsonl` is
byte-identical across runs. Wall-clock data lives only in `manifest.json`.

## Reading the results

Primary metrics are dimensional; read them as a profile rather than a ranking:

- **Decision accuracy** - overall agreement with ground truth. Always report with
  the per-class split: evaluators can trade valid-class accuracy against
  review-class handling.
- **Mutation detection rate** - of cases where a mutation *should* change the triage
  decision, how often the evaluator followed. Low values mean degraded reports pass
  unchallenged.
- **False reassurance rate** - the headline risk metric: accepting content that
  should not be accepted.
- **Over-rejection rate** - how often valid reports are rejected outright.
- **Robustness delta (drift)** - decision wobble on quality-neutral edits
  (professionalization, noise). High drift means presentation moves the verdict.
- **Presentation susceptibility** - acceptance gained by polished-but-broken
  variants over their canonical parents.
- **Calibration error** - whether stated confidence tracks actual correctness.
- **Error taxonomy** - which *kind* of mistake dominates. Two evaluators with equal
  accuracy but different taxonomies fail differently; that difference matters more
  than the accuracy gap for deployment decisions.

The auxiliary Robustness Score is a convenience summary only; never quote it alone.

## v0.2 study snapshot

On this exact corpus and seed (`deterministic-study-v0.2`, 340 cases):

- rules-baseline: accuracy 0.824, detection 0.802, FAR 0.088 - suspicion-driven,
  strong at catching degradations, prone to over-strict rejects on borderline-invalid
  prose.
- evidence-graph-baseline: accuracy 0.547, detection 0.000, FAR 0.438 -
  structure-driven: a complete claim-evidence graph earns trust even when claim
  quality has been degraded. Competitive on review-class fixtures (hedging breaks
  its accept path).

Full details: docs/evaluator-study-v0.2.md, including the V26 results audit
(docs/v26-results-audit.md) that root-caused the negative control's blindness.
