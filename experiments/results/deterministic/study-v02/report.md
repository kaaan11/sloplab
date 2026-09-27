# Evaluator study: deterministic-study-v0.2

> Primary accuracy interval: 95% cluster bootstrap over logical-report
> clusters (52 logical-report clusters); estimand: within this fixed synthetic collection,
> treating logical-report clusters as exchangeable. The cluster count
> is not an effective sample size. Row-level CI shown second.

## `evidence-graph-baseline`

- Decision accuracy: **0.542** (95% cluster bootstrap CI 0.4581-0.6300) (row-level bootstrap CI 0.485-0.596)
- Mutation detection rate: 0.125
- False reassurance rate: **0.42857142857142855**
- Over-rejection rate: 0.0
- Robustness delta (drift): 0.0
- Presentation susceptibility: 0.0
- Calibration error (ECE): 0.27011784511784503
- Accuracy by report class:
    - invalid: 0.531
    - review: 0.741
    - valid: 0.432
    - canonical_overall: 0.750
- Error taxonomy:
    - deferred_invalid: 20
    - false_reassurance: 22
    - over_strict_reject: 11
    - premature_accept: 83

## `rules-baseline`

- Decision accuracy: **0.848** (95% cluster bootstrap CI 0.7857-0.9020) (row-level bootstrap CI 0.805-0.889)
- Mutation detection rate: 0.8020833333333334
- False reassurance rate: **0.09387755102040816**
- Over-rejection rate: 0.0
- Robustness delta (drift): 0.0070921985815602835
- Presentation susceptibility: 0.0
- Calibration error (ECE): 0.33851515151515155
- Accuracy by report class:
    - invalid: 0.719
    - review: 0.941
    - valid: 0.851
    - canonical_overall: 0.833
- Error taxonomy:
    - deferred_invalid: 8
    - false_reassurance: 22
    - over_strict_reject: 11
    - premature_accept: 1
    - premature_deferral: 3

## Paired comparison

- `evidence-graph-baseline` vs `rules-baseline`: 8 wins / 99 losses / 190 ties (win rate 0.075)
- Paired difference, same resample (`evidence-graph-baseline - rules-baseline`): **0.3050** (95% CI 0.2027-0.4000)
