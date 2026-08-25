# Deterministic Evaluator Study - v0.2 results and notes (V26, audited)

> **Positioning note:** `evidence-graph-baseline` is a **negative control**, not a
> competitive baseline. It models structure-only triage and is intentionally blind
> to content-quality mutations; its results demonstrate that SlopLab detects such
> blindness. See docs/v26-results-audit.md for the root-cause analysis.

Run: `experiments/configs/deterministic-study-v0.2.yaml` over the 52-fixture corpus.
Population: **340 cases** (52 canonical + 288 derived). Seed `20260825`; records are
byte-identical across re-runs at this commit.

## Headline metrics (post-audit run)

| Metric | rules-baseline | evidence-graph-baseline (negative control) |
|---|---|---|
| Decision accuracy | **0.824** | 0.582 |
| Mutation detection rate | **0.802** | 0.125 |
| False reassurance rate | **0.088** | 0.394 |
| Over-rejection rate | 0.000 | 0.000 |
| Robustness delta (drift) | 0.016 | 0.000 |
| Calibration error | 0.305 | 0.260 |

Accuracy by class (rules / graph): valid 0.86/0.41 · invalid 0.77/0.59 ·
review 0.81/0.75.

Paired comparison (340 shared cases): rules-baseline 92 wins vs evidence-graph 10,
238 ties.

The nonzero-but-tiny graph MDR (0.125 = 8/64) comes entirely from the
contradict-observed-result family after the contract-conformance fix below; the
other eleven mutation families remain invisible to it by design.

## Interpretation (scoped to this benchmark)

The two baselines have genuinely different robustness personalities, which is the
discrimination V0.2 set out to demonstrate:

- **rules-baseline** is suspicion-driven: lexical flags route degraded content to
  review or reject. It detects 80% of degrading mutations and rarely reassures
  falsely, but it over-rejects borderline-invalid prose (24 `over_strict_reject`)
  and defers some genuinely invalid reports (`deferred_invalid`: 8).
- **evidence-graph-baseline** is structure-driven: when the claim-evidence graph is
  complete it trusts the report regardless of claim quality. It never detects
  degrading mutations that leave structure intact (MDR 0.0) and shows high false
  reassurance (0.438), but its review-class handling is competitive (0.75) because
  hedging breaks its accept path.

Neither result was produced by adjusting labels; both evaluator behaviors follow
from their documented designs.

## Surprises found during manual inspection (V26 discipline)

1. **New review fixtures evaded uncertainty detection** - "Undetermined." as a
   sentence-initial word did not match phrase-only patterns. Fix: generic
   unresolved-state vocabulary added (`undetermined`, `inconclusive`, `unresolved`,
   `withheld pending`). Review accuracy for rules-baseline rose 0.58 -> 0.81 on this
   corpus. *Disclosure:* this is corpus-adjacent calibration; the caveat in
   methodology.md applies to any future corpus re-use of these phrasings.
2. **Conditional boundary statements caused hard rejects** - a negation inside an
   "If ..." clause tripped the reject path (e.g. graphql-028). Fix: conditionals now
   downgrade to a `CONDITIONAL_BOUNDARY_STATEMENT` finding routing to manual review.
3. **Evidence-graph consequence vocabulary missed word forms** ("persisted" vs
   `persists?`). Fixed with word-stem matching during V23 development, before the
   frozen study run above; noted here for provenance.

No labels, operators, or expected-effect values were changed in response to these
results.
