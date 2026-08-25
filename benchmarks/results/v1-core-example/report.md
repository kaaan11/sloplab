# SlopLab benchmark: v1-core

## Evaluator: `oracle`

- Cases scored: 250
- Decision accuracy: 1.000
- False reassurance rate: 0.000 (0 cases)
- Over-rejection rate: 0.000 (0 cases)
- Mutation detection rate: 1.000 (of 64 degrading mutations)
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

- Cases scored: 250
- Decision accuracy: 0.808
- False reassurance rate: 0.126 (26 cases)
- Over-rejection rate: 0.000 (0 cases)
- Mutation detection rate: 0.766 (of 64 degrading mutations)
- Robustness delta (canonical - mutated): +0.014
- Presentation susceptibility: -0.024
- Calibration error (ECE): 0.313
- Dimension MAE:
  - claim_evidence_consistency: 0.435
  - evidence_completeness: 0.291
  - impact_calibration: 0.504
  - reproducibility: 0.231
  - scope_consistency: 0.371
- Accuracy by report class:
  - invalid: 0.768
  - review: 0.817
  - valid: 0.833
  - canonical_overall: 0.771
- Auxiliary Robustness Score: 0.8146
