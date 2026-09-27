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
| `analysis.json` | bundles, paired comparisons, error taxonomy, cluster bootstrap accuracy CIs + paired difference (primary), row-level bootstrap CIs (compat) |
| `report.md` | human-readable summary |
| `results.csv` | flat per-case table |

Byte-identity contract: for a fixed commit + corpus + seed, `records.jsonl` is
byte-identical across runs. Wall-clock data lives only in `manifest.json`.

## Reading the results

Primary metrics are dimensional; read them as a profile rather than a ranking:

- **Decision accuracy** - overall agreement with ground truth. Always report with
  the per-class split: evaluators can trade valid-class accuracy against
  review-class handling.
- **Decision-changing target accuracy** (formerly "mutation detection rate") - of
  cases where a mutation *should* change the triage decision, how often the
  evaluator followed. Low values mean degraded reports pass unchallenged.
  Caveat (#45): a blind always-`needs_manual_review` policy scores 0.760 on this
  metric (rules-baseline 0.802); report it only against that floor.
- **False reassurance rate** - the headline risk metric: accepting content that
  should not be accepted.
- **Over-rejection rate** - how often valid reports are rejected outright.
- **Decision-preserving drift** (formerly "Robustness delta") - decision wobble on
  decision-preserving mutations. High drift means presentation moves the verdict.
- **Presentation susceptibility** - acceptance gained by polished-but-broken
  variants over their canonical parents (operator-generated presentation
  mutations only; the authored plain/polished pairs are not in this population,
  #50).
- **Calibration error** - whether stated confidence tracks actual correctness.
- **Error taxonomy** - which *kind* of mistake dominates. Two evaluators with equal
  accuracy but different taxonomies fail differently; that difference matters more
  than the accuracy gap for deployment decisions.

The auxiliary Robustness Score is a convenience summary only; never quote it alone
or use it for ranking: a blind always-`needs_manual_review` policy scores 0.740
on it (rules-baseline 0.839) on this corpus (#45); reproduce with
`uv run python scripts/blind_policy_compare.py`.

## v0.2 study snapshot (numbers regenerated at PR #33 / #20)

On this exact corpus and seed (`deterministic-study-v0.2`, 297 cases after the
v0.2.2 no-op exclusion):

- rules-baseline: decision-changing target accuracy 0.802 (formerly reported as
  "detection 0.802"), decision accuracy 0.848, false reassurance 0.094 -
  suspicion-driven, strong on decision-changing cases, prone to over-strict
  rejects on borderline-invalid prose (11 `over_strict_reject` after PR #33).
- evidence-graph-baseline: decision accuracy 0.542, decision-changing target
  accuracy 0.125, false reassurance 0.429 - structure-driven: a complete
  claim-evidence graph earns trust even when claim quality has been degraded.
  Competitive on review-class fixtures (hedging breaks its accept path).

Full details: docs/evaluator-study-v0.2.md, including the V26 results audit
(docs/v26-results-audit.md) that root-caused the negative control's blindness.
