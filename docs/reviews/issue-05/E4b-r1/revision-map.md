# E4b-r1 — Revizyon haritası (revision-map.md)

E4b kabul kararındaki her bulgu → R1 karşılığı (dosya + test):

## Bloklayıcı 1 — failed coverage doğrulanmıyor

- Zarf `outcomes` bağını taşır: varlık/yokluk, yol, SHA-256, satır sayısı
  (`reporting/analysis.py:write_versioned_analysis`). Yayın sırasında
  `scored + failed + not_run == planned` denkliği zorunludur; tutmazsa
  yayın başarısız olur.
- Okuyucu records + outcomes satırlarından evaluator kümesini,
  scored/failed sayılarını, vaka kimliklerini, tekillik/çakışma durumunu
  ve planlanan birliği (suite index eşitliği) yeniden türetir
  (`_verify_accounting`).
- Karşıörnek (`failed=999` + taze completion): `test_failed_count_tamper_rejected`
  ile reddedilir.

## Bloklayıcı 2 — tamamen başarısız evaluator görünmez oluyor

- CLI study evaluator birliğini records + failed satırlarından kurar;
  sıfır-başarılı evaluator `compute_metrics([], name)` paketiyle korunur
  (`scored=0`, `failed=N`, tanımsız metrik nedenleri; uydurma kayıt yok).
- Karşıörnek (her vakada `EvaluationFailure`): `test_all_failed_evaluator_preserved`
  ve `test_mixed_partial_study_equations` ile görünür; compare/report
  kontrollü işler.

## Bloklayıcı 3 — gömülü metrikler yeniden doğrulanmıyor

- Okuyucu her evaluator için bağlı records üzerinden güncel tanımla
  bundle'ları yeniden hesaplar ve gömülü değerlerle birebir karşılaştırır
  (`_verify_recomputed_bundles`); `decision_accuracy 0.123456` + taze
  completion karşıörneği `test_embedded_metric_tamper_rejected` ile reddedilir.
- Zarf şeması `1 → 2` (outcomes bağı + planned/not_run coverage); tanım
  sürümü `1` (formüller değişmedi). Şema-1 belgeler yeniden hesaplamaya
  yönlendirilir.

## Ek kapanan karşıörnekler

- Outcomes satır düşmesi/silinmesi/dikilmesi/yabancı dosya/duplicate/
  scored-failed çakışması/not_run satırı/evaluator-liste/planlanan-birlik
  oynamaları: `test_outcomes_*`, `test_duplicate_*`,
  `test_scored_failed_collision_rejected`, `test_not_run_row_rejected`,
  `test_evaluator_list_tamper_rejected`, `test_planned_union_mismatch_rejected`.
- `analysis.json` ve tarihsel artefaktlar değişmedi; estimand/ağırlık/CI
  eklenmedi. E4a repeat-scoped parent eşlemesi ve E3 strict publish sınırı
  aynen korunur (tam paket yeşil).
