# Evaluator study: deterministic-study-v0.2

## `evidence-graph-baseline`

- Decision accuracy: **0.582** (95% bootstrap CI 0.532-0.635)
- Mutation detection rate: 0.125
- False reassurance rate: **0.39416058394160586**
- Over-rejection rate: 0.0
- Robustness delta (drift): 0.0
- Presentation susceptibility: 0.013305322128851549
- Calibration error (ECE): 0.2357588235294117
- Accuracy by report class:
    - invalid: 0.585
    - review: 0.750
    - valid: 0.481
    - canonical_overall: 0.750
- Error taxonomy:
    - deferred_invalid: 22
    - false_reassurance: 24
    - over_strict_reject: 12
    - premature_accept: 84

## `rules-baseline`

- Decision accuracy: **0.824** (95% bootstrap CI 0.782-0.865)
- Mutation detection rate: 0.8020833333333334
- False reassurance rate: **0.08759124087591241**
- Over-rejection rate: 0.0
- Robustness delta (drift): 0.005434782608695652
- Presentation susceptibility: -0.030812324929971976
- Calibration error (ECE): 0.2836529411764706
- Accuracy by report class:
    - invalid: 0.768
    - review: 0.812
    - valid: 0.858
    - canonical_overall: 0.800
- Error taxonomy:
    - deferred_invalid: 8
    - false_reassurance: 23
    - over_strict_reject: 24
    - premature_accept: 1
    - premature_deferral: 4

## Paired comparison

- `evidence-graph-baseline` vs `rules-baseline`: 10 wins / 92 losses / 238 ties (win rate 0.098)
