# E4b — Operatör-metrik uygunluğu (operator-metric-eligibility.md)

Kaynak: `reporting/analysis.py:operator_metric_eligibility()` (kayıtlı her
operatörü koddan türetir; tablo çıktısı aşağıya yapıştırıldı).
`degrading_capable` operatör spec'inden (`decision_by_parent_class`
boş değilse), `presentation` paylaşılan presentation kümesinden okunur.
Drift uygunluğu operatöre değil vakaya bağlıdır (beklentisi değişmeyen
nötr düzenleme); parent gerektiren alt gruplar aynı girdide ebeveyn
satırı ister, sağlanamazsa çift `pairs_unresolved` sayılır ve metrik
gerekçeli tanımsız olur.

| operator | category | degrading | presentation | detection | susceptibility | invariance |
| --- | --- | --- | --- | --- | --- | --- |
| add_irrelevant_detail | noise | 0 | 0 | 0 | 0 | no expectation change by spec; drift near zero is stability signal only, never quality approval |
| confidence_overstatement | presentation | 0 | 1 | 0 | 1 | acceptance gain on still-broken content is susceptibility signal; unchanged decisions prove nothing about quality |
| contradict_observed_result | evidence_contradiction | 1 | 0 | 1 | 0 | unchanged decisions on degrading edits are detection misses, not robustness evidence |
| fabricate_reference | reference | 1 | 0 | 1 | 0 | unchanged decisions on degrading edits are detection misses, not robustness evidence |
| impact_inflation | impact | 1 | 0 | 1 | 0 | unchanged decisions on degrading edits are detection misses, not robustness evidence |
| impossible_precondition | technical_consistency | 1 | 0 | 1 | 0 | unchanged decisions on degrading edits are detection misses, not robustness evidence |
| invent_api_identifier | technical_consistency | 1 | 0 | 1 | 0 | unchanged decisions on degrading edits are detection misses, not robustness evidence |
| misattribute_cve | reference | 1 | 0 | 1 | 0 | unchanged decisions on degrading edits are detection misses, not robustness evidence |
| professionalize_language | presentation | 0 | 1 | 0 | 1 | acceptance gain on still-broken content is susceptibility signal; unchanged decisions prove nothing about quality |
| remove_affected_version | evidence_removal | 0 | 0 | 0 | 0 | no expectation change by spec; drift near zero is stability signal only, never quality approval |
| remove_reproduction_step | evidence_removal | 1 | 0 | 1 | 0 | unchanged decisions on degrading edits are detection misses, not robustness evidence |
| scope_expansion | impact | 1 | 0 | 1 | 0 | unchanged decisions on degrading edits are detection misses, not robustness evidence |

## Yorum kuralları

- **Karar değişmezliğini kalite nötrlüğü olarak yorumlama.**
  Degrading düzenlemede değişmeyen karar detection ıskasıdır;
  presentation düzenlemede değişmeyen karar kalite kanıtı değildir;
  drift≈0 yalnız kararlılık sinyalidir, kalite onayı değildir.
- Accuracy/false-reassurance/over-rejection/ECE/MAE bütün operatörlerin
  kayıtlarında çalışır (kayıt düzeyi); yukarıdaki sütunlar yalnızca
  operatöre özgü alt-grup metriklerin (detection/susceptibility)
  uygunluğunu ve drift çift bağlamını belirtir.
- Yeni operatör eklenirse tablo kodu otomatik kapsar
  (`test_eligibility_covers_every_registered_operator` bekçidir).
