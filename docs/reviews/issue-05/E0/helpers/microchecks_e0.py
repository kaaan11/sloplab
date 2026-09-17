"""E0 mikro doğrulamaları: U2 severity üyeliği + U3 karışık-bin ECE (teslim dizininde yaşar).

Kullanım (repo kökünden, ağsız):
  uv run --offline --frozen python docs/reviews/issue-05/E0/helpers/microchecks_e0.py

U2: adapter.py:178 `severity in Severity.__members__` üye ADLARINI (BÜYÜK HARF)
sınar; normal "high" değeri tutmaz -> MEDIUM'a düşer, "HIGH" ise
Severity("HIGH") değer aramasında ValueError verir.
U3: metrics.py:172-174 son bini yalnız boşsa kapatır; [0.9,1.0) + 1.0 karışık
durumunda 1.0 dışarıda kalır. Beklenen: ECE 0.025 (düşmüş), 0.475 değil.
"""

from sloplab.models.enums import Severity

print("Severity members:", list(Severity.__members__.keys()))
print("Severity values:", [m.value for m in Severity])
# U2: lowercase 'high' membership test as in adapter.py:178
for s in ["high", "HIGH", "medium", "critical", "info"]:
    print(s, "in __members__?", s in Severity.__members__)
    try:
        print("  Severity(s) =", Severity(s))
    except Exception as e:
        print("  Severity(s) raises:", type(e).__name__, e)
# U3: mixed last-bin ECE: one record in [0.9,1.0), one correct at 1.0
from sloplab.models.enums import Decision
from sloplab.models.run import CaseRecord
from sloplab.models.evaluation import DimensionScores, EvaluationResult
from sloplab.scoring.metrics import compute_calibration_error


def rec(conf, correct, cid):
    dims = {d: 0.9 for d in ["reproducibility", "evidence_completeness",
                             "claim_evidence_consistency", "impact_calibration",
                             "scope_consistency"]}
    r = EvaluationResult(evaluator_name="t", evaluator_version="0", case_id=cid,
                         decision=Decision.ACCEPT, confidence=conf,
                         dimensions=DimensionScores.from_dict(dims))
    exp = Decision.ACCEPT if correct else Decision.REJECT
    return CaseRecord.from_result(r, case_id=cid, case_kind="canonical",
                                  report_class="valid", expected_decision=exp)


mixed = [rec(0.95, True, "a"), rec(1.0, False, "b")]
print("mixed-bin ECE (0.95/correct + 1.0/wrong):", compute_calibration_error(mixed))
print("expected if both counted: |0.975-0.5| =", abs(0.975 - 0.5))
print("expected if 1.0 dropped: |0.95-1.0|*1/2 =", abs(0.95 - 1.0) * 0.5)
# U4 pure-weight demo is analytic; confirm formula shape only
