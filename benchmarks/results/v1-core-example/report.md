# SlopLab benchmark: v1-core

## Evaluator: `oracle`

- Cases scored: 297
- Decision accuracy: 1.000
- False reassurance rate: 0.000 (0 cases)
- Over-rejection rate: 0.000 (0 cases)
- Mutation detection rate: 1.000 (of 96 degrading mutations)
- Robustness delta (canonical - mutated): +0.000
- Presentation susceptibility: +0.000
- Calibration error (ECE): 0.000
- Dimension MAE:
  - claim_evidence_consistency: 0.000
  - evidence_completeness: 0.000
  - impact_calibration: 0.000
  - reproducibility: 0.000
  - scope_consistency: 0.000
- Accuracy by report class:
  - invalid: 1.000
  - review: 1.000
  - valid: 1.000
  - canonical_overall: 1.000
- Auxiliary Robustness Score: 1.0000

## Evaluator: `rules-baseline`

- Cases scored: 297
- Decision accuracy: 0.811
- False reassurance rate: 0.094 (23 cases)
- Over-rejection rate: 0.000 (0 cases)
- Mutation detection rate: 0.802 (of 96 degrading mutations)
- Robustness delta (canonical - mutated): +0.007
- Presentation susceptibility: -0.019
- Calibration error (ECE): 0.298
- Dimension MAE:
  - claim_evidence_consistency: 0.368
  - evidence_completeness: 0.280
  - impact_calibration: 0.423
  - reproducibility: 0.243
  - scope_consistency: 0.325
- Accuracy by report class:
  - invalid: 0.719
  - review: 0.812
  - valid: 0.851
  - canonical_overall: 0.800
- Auxiliary Robustness Score: 0.8393
