# E4b — Sürümlü analiz yayını ve tarihsel yeniden hesaplama

Önkoşul: [E4a kabulü](../E4a-acceptance.md) (inceleyici düzeltmeli).
Ortak kurallar: [worker teslim protokolü](../../issue-05-worker-delivery-protocol.md).
Önceki kanıtlar değiştirilmedi. Canlı pilot ilan edilmedi.

## Uygulanan davranış

- Yeni `reporting/analysis.py`: `ANALYSIS_DEFINITION_VERSION = 1`,
  `write_versioned_analysis` (ayrı ad `analysis-v1.json`; kayıt bayt
  hash'i + coverage + tanım sürümüyle bağlı), `read_versioned_analysis`
  (zarf/tanım sürümü → paket `complete` → kayıt hash/satır/evaluator
  coverage tutarlılığı; stale/karışık/coverage/sürüm ihlali
  `AnalysisError` yükseltir), `operator_metric_eligibility` (koddan
  türetilmiş uygunluk tablosu).
- CLI `study` sürümlü yayını üretir (`analysis.json` aynen korunur);
  CLI `compare` dizindeki tek sürümlü analizi doğrulanmış tüketir
  (çoksa açık hata; yoksa legacy yol); CLI `report --analysis` aynı
  belgeyi yeniden türetmeden işler. Legacy girdiler eski yoldan okunur.
- Drift docstring'ine değişmezlik-okuma kuralı eklendi (davranışsız).
- Korunanlar: comparison.py/CI yöntemleri, estimand/ağırlık seçimleri
  (yapılmadı), tarihsel dosyalar. Yeni bilimsel tercih ilan edilmedi.

## Değişen / yeni dosyalar

- Yeni: `reporting/analysis.py`, `test_versioned_analysis.py` (9),
  `test_historical_recomputation.py` (3),
  `test_operator_eligibility.py` (2).
- Değişen: `cli/main.py` (study/compare/report), `scoring/metrics.py`
  (2 satır docstring; `start/metrics.py` snapshot'ı bu cümleden
  rekonstrükedir, tekabül eden düzenleme birebir eşleşmeyle uygulandı).
- Dokunulmayan: `writers.py`, mevcut testler.
- Belgeler: `analysis-version-contract.md`,
  `legacy-vs-current-analysis.md`, `operator-metric-eligibility.md`.

## Test / doğrulama

- Hedefli küme: **245 passed**. Tam offline paket: **353 passed**
  (339 + 14). ruff check/format, mypy temiz. Sıfır canlı istek.
- Tarihsel recompute: committed örnek deterministik eşit; farklar yalnız
  paired fix (rules susc.) + coverage zarfı, hepsi gerekçeli. E1e tablosu
  belgede (susc. sıfırlandı, robustness_score türev etkisi kayıtlı).

## Deterministik study

Yeni benzersiz kök `/tmp/sloplab-e4b-R3wpUI` (297 cases, 2 evaluators;
594 kayıt). E1e'ye göre: üç şema eki + iki düzeltilmiş türev; ortak 478
hash IDENTICAL, kayıtlar/manifesto bayt-eşit. Yeni paket `complete`
(485 dosya); sürümlü okuma OK; `run-outputs.sha256` 485/485 doğrulandı.
`/tmp` kalıcı arşiv değildir.
