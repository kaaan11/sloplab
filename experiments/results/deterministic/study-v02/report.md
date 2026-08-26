# Evaluator study: deterministic-study-v0.2

## `evidence-graph-baseline`

- Decision accuracy: **0.542** (95% bootstrap CI 0.485-0.596)
- Mutation detection rate: 0.125
- False reassurance rate: **0.42857142857142855**
- Over-rejection rate: 0.0
- Robustness delta (drift): 0.0
- Presentation susceptibility: 0.006787330316742085
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

- Decision accuracy: **0.811** (95% bootstrap CI 0.768-0.855)
- Mutation detection rate: 0.8020833333333334
- False reassurance rate: **0.09387755102040816**
- Over-rejection rate: 0.0
- Robustness delta (drift): 0.0070921985815602835
- Presentation susceptibility: -0.018853695324283576
- Calibration error (ECE): 0.2977744107744108
- Accuracy by report class:
    - invalid: 0.719
    - review: 0.812
    - valid: 0.851
    - canonical_overall: 0.800
- Error taxonomy:
    - deferred_invalid: 8
    - false_reassurance: 22
    - over_strict_reject: 22
    - premature_accept: 1
    - premature_deferral: 3

## Paired comparison

- `evidence-graph-baseline` vs `rules-baseline`: 8 wins / 88 losses / 201 ties (win rate 0.083)
