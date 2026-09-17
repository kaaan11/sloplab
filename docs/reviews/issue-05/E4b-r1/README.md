# E4b-r1 — Outcomes bağlı coverage ve yeniden doğrulanan metrikler

Önkoşul: [E4b revizyon kararı](../E4b-acceptance.md). Ortak kurallar:
[worker teslim protokolü](../../issue-05-worker-delivery-protocol.md).
Önceki kanıtlar değiştirilmedi. Canlı pilot ilan edilmedi.

## Uygulanan davranış

- Zarf şeması `1 → 2`: outcomes bağı (varlık/yokluk + yol + SHA-256 +
  satır) ve evaluator başına `{planned, scored, failed, not_run}`
  coverage; tanım sürümü `1` (formüller değişmedi). Şema-1 belgeler
  yeniden hesaplamaya yönlendirilir.
- Yayın denkliği yayında zorunlu (`scored + failed + not_run ==
  planned`); tutmazsa yayın başarısız olur. CLI study evaluator birliğini
  records + failed satırlarından kurar; sıfır-başarılı evaluator
  `compute_metrics([], name)` paketiyle korunur (uydurma kayıt yok).
- Okuyucu yeniden türetir: evaluator kümesi, sayılar, vaka kimlikleri,
  tekillik/çakışma, planlanan birlik (suite index eşitliği); her gömülü
  E4a demetini bağlı records üzerinden güncel tanımla birebir doğrular.
  Stale/karışık/coverage/sürüm ihlali `AnalysisError` yükseltir.
- Korunanlar: `analysis.json` ve tarihsel artefaktlar, E4a parent eşlemesi,
  E3 strict publish sınırı, estimand/ağırlık/CI tercihsizliği.

## Değişen / yeni dosyalar

- `reporting/analysis.py` (zarf v2 + tam yeniden-doğrulama),
  `cli/main.py` (birlik coverage + sıfır-başarılı paketler).
- Yeni testler (13): `tests/regression/test_analysis_binding.py`
  (3 karşıörnek + 10 sınır/denklik testi).
- Dokunulmayan: E4b testleri, `comparison.py`, `writers.py`.
- Belgeler: `revision-map.md`, güncellenmiş
  `analysis-version-contract.md` (E4b belgesi dondurulmuş olarak kalır).

## Test / doğrulama

- Üç karşıörnek de reddedilir (`failed=999`, görünmez evaluator,
  `accuracy=0.123456` — taze completion'a rağmen).
- Hedefli küme: **258 passed** (245 + 13 yeni). Tam offline paket:
  **366 passed** (353 + 13). Sayılar collect/run çıktılarıyla birebir
  (13 = 13 tek dosya; baz 353). ruff check/format, mypy temiz. Sıfır
  canlı istek.

## Deterministik study

Yeni benzersiz kök `/tmp/sloplab-e4b-r1-WI9ueE` (297 cases, 2
evaluators; 594 kayıt). E1e'ye göre: üç şema eki + iki düzeltilmiş
türev; ortak 478 hash IDENTICAL, kayıtlar bayt-eşit. Yeni paket
`complete` (485 dosya); sürümlü okuma OK (şema 2, outcomes yokluğu
bağlı); `run-outputs.sha256` 485/485 doğrulandı. `/tmp` kalıcı arşiv
değildir.
