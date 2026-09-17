# E4b-r1 — Analiz sürüm sözleşmesi (analysis-version-contract.md)

E4b sözleşmesi devralındı; R1 ekleri yıldızlıdır.

## Sürümlü yayın

Study, `analysis.json` yanına ayrı adla sürümlü analiz yazar:
`analysis-vN.json` (`N = ANALYSIS_DEFINITION_VERSION`, bugün `1`).
Tarihsel `analysis.json` ne üzerine yazılır ne değiştirilir.

Sürüm belgesi türü, kaynak kayıt kümesinin hash'i, ★ outcomes kaynağı
(varlık/yokluk + yol + SHA-256 + satır sayısı), ★ evaluator başına
`{planned, scored, failed, not_run}` selection/outcome coverage'ı ve
analiz tanım sürümüyle ayrışamaz; birlikte taşınır. Study yolunda
`not_run` açık `0` yazılır. Yayın, `scored + failed + not_run ==
planned` denkliğini baştan sağlar.

- Zarf şeması ★ `2` (outcomes bağı + planned/not_run coverage);
  tanım sürümü `1` (formüller değişmedi). Şema-1 belgeler yeniden
  hesaplamaya yönlendirilir.
- Tanım değişen her formül/uygunluk revizyonu tanım sürümünü artırır.
  Okuyucu yalnız güncel ikiliyi kabul eder.

## Tüketici kapısı (`read_versioned_analysis`)

Sırayla: ayrıştırma → bilinen zarf/tanım sürümü → paket `complete` →
kayıt bağı (hash/satır) → ★ outcomes bağı (yoklukta dikili dosya dahil)
→ ★ evaluator kümesi/sayı/kimlik/tekillik/çakışma/planlanan-birlik
yeniden türetimi (suite index eşitliği) → ★ bağlı records üzerinden
güncel tanımla metrik demetlerinin birebir yeniden doğrulanması.
Sıfır-başarılı evaluator `scored=0`, `failed=N` ve tanımsız metrik
nedenleriyle korunur (uydurma kayıt yok). İlk ihlal `AnalysisError`
yükseltir: stale cache, karışık analiz/kayıt, coverage uyuşmazlığı,
sürüm değişimi.

CLI `study` sürümlü yayını üretir; CLI `compare` (dizindeki tek
sürümlü analizi doğrulanmış tüketir; çoksa açık hata) ve CLI `report
--analysis` aynı belgeyi yeniden türetmeden işler. Legacy girdiler eski
yoldan, açık notla okunmaya devam eder. Yeni nihai bilimsel tercih
yoktur.
