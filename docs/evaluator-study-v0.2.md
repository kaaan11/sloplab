# Deterministic Evaluator Study - v0.2 results (regenerated at v0.2.2)

> **Live LLM scope statement (V0.2 closure):** the live LLM experiment was NOT
> executed in V0.2. The strict-JSON adapter, its mock-based failure tests, and the
> full experiment/reproducibility infrastructure are implemented and green; running
> the pilot requires only adding the `llm-bench` environment secret and remains a
> documented future opt-in study (docs/backlog.md, docs/llm-pilot-runbook.md).

> **Positioning note:** `evidence-graph-baseline` is a **negative control**, not a
> competitive baseline. It models structure-only triage and is intentionally blind
> to content-quality mutations; its results demonstrate that SlopLab detects such
> blindness. See docs/v26-results-audit.md for the root-cause analysis.

> **v0.2.2 regeneration:** the artifacts in
> `experiments/results/deterministic/study-v02/` were regenerated at v0.2.2 after
> the independent v0.2.1 audit. 43 confidence-overstatement plans that produced no
> textual change had been written as "mutated" clones of their parents; they are
> now excluded (R01). Population: **297 cases** (60 canonical + 237 derived).
> Seed `20260825`; records remain byte-identical across re-runs at this commit.
> All numbers below were recomputed from the regenerated records.

## Headline metrics (post-audit run)

| Metric | rules-baseline | evidence-graph-baseline (negative control) |
|---|---|---|
| Decision accuracy | **0.811** | 0.542 |
| Mutation detection rate | **0.802** (77/96) | 0.125 (12/96) |
| False reassurance rate | **0.094** (23 cases) | 0.429 (105 cases) |
| Over-rejection rate | 0.000 | 0.000 |
| Robustness delta (drift) | 1/141 = 0.007 | 0/141 = 0.000 |
| Calibration error | 0.298 | 0.270 |

Accuracy by class (rules / graph): valid 0.85/0.43 · invalid 0.72/0.53 ·
review 0.81/0.74; canonical-only accuracy 0.80 / 0.75.

95% seeded-bootstrap accuracy CIs: rules-baseline 0.768-0.855,
evidence-graph-baseline 0.485-0.596.

Paired comparison (297 shared cases): rules-baseline 88 wins vs evidence-graph 8,
201 ties.

The graph's nonzero-but-tiny MDR (12/96 = 0.125) comes from the
contradict-observed-result family (11/11) plus one borderline
remove-reproduction-step case (1/10) whose two-step support floor is broken by the
mutation; the remaining six degrading families in the detection population stay at
zero by design (fabricate-reference 0/14, impact-inflation 0/11,
impossible-precondition 0/12, invent-api-identifier 0/13, misattribute-cve 0/13,
scope-expansion 0/12).

## Interpretation (scoped to this benchmark)

The two baselines have genuinely different robustness personalities, which is the
discrimination V0.2 set out to demonstrate:

- **rules-baseline** is suspicion-driven: lexical flags route degraded content to
  review or reject. It detects 80% of degrading mutations and rarely reassures
  falsely, but it over-rejects borderline-invalid prose (22 `over_strict_reject`)
  and defers some genuinely invalid reports (`deferred_invalid`: 8).
- **evidence-graph-baseline** is structure-driven: when the claim-evidence graph is
  complete it trusts the report regardless of claim quality. It detects none of the
  content-quality families that leave graph structure intact and shows high false
  reassurance (0.429), but its review-class handling is competitive (0.74) because
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
