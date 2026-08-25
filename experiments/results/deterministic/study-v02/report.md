# Evaluator study: deterministic-study-v0.2

## `evidence-graph-baseline`

- Decision accuracy: **0.547** (95% bootstrap CI 0.497-0.597)
- Mutation detection rate: 0.0
- False reassurance rate: **0.43795620437956206**
- Over-rejection rate: 0.0
- Robustness delta (drift): 0.0
- Presentation susceptibility: 0.013305322128851549
- Calibration error (ECE): 0.259570588235294
- Accuracy by report class:
    - invalid: 0.585
    - review: 0.750
    - valid: 0.407
    - canonical_overall: 0.750
- Error taxonomy:
    - deferred_invalid: 22
    - false_reassurance: 35
    - over_strict_reject: 12
    - premature_accept: 85

## `rules-baseline`

- Decision accuracy: **0.759** (95% bootstrap CI 0.715-0.806)
- Mutation detection rate: 0.8020833333333334
- False reassurance rate: **0.1678832116788321**
- Over-rejection rate: 0.0
- Robustness delta (drift): 0.016304347826086956
- Presentation susceptibility: -0.008403361344537813
- Calibration error (ECE): 0.3052176470588235
- Accuracy by report class:
    - invalid: 0.768
    - review: 0.583
    - valid: 0.858
    - canonical_overall: 0.733
- Error taxonomy:
    - deferred_invalid: 8
    - false_reassurance: 23
    - over_strict_reject: 24
    - premature_accept: 23
    - premature_deferral: 4

## Paired comparison

- `evidence-graph-baseline` vs `rules-baseline`: 26 wins / 98 losses / 216 ties (win rate 0.210)
