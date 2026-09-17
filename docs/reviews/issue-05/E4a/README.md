# E4a — Metrik sözleşmeleri ve analitik karşıörnek düzeltmeleri

Önkoşul: [E3b-r1 kabulü ve E3 kapanışı](../E3b-r1-acceptance.md). Ortak
kurallar: [worker teslim protokolü](../../issue-05-worker-delivery-protocol.md).
Önceki kanıtlar değiştirilmedi. Canlı pilot ilan edilmedi.

## Uygulanan davranış

- **Susceptibility (paired)**: grup-oran farkı yerine çift başına
  `child−parent` ortalaması. Her çift anlaşıyorsa sonuç tam `0`
  (çocuk dağılımından bağımsız). Ebeveyn bağı yoksa neden belirten
  tanımsızlık. Case-weighted betimsel sözleşme açıkça adlandırıldı.
- **ECE**: son bin her zaman sağdan kapalı; `1.0` bin arkadaşlarıyla
  sayılır; her aralık-içi kayıt tam bir bine girer. Aralık-dışı/NaN
  sayılır, paydadan sessizce düşmez.
- **Reader sınırı** (`validate_metric_records`, `compute_metrics`
  girişinde): tekillik, `correct` uyumu, legacy failed işaretleri ve
  mutated parent/operator bağları ihlalde `ValueError` yükseltir.
  Failed/not_run outcome'lar doğruluk/ECE/birliğe girmez.
- **Coverage**: her metrik `metric_coverage` altında uygunluk/sayımlar ve
  `undefined_reason` taşır (drify çiftleri, ECE binned/out-of-range,
  beklentisiz sayımları dahil).
- Korunanlar: ham karar/hedef kayıtları, drift formülü değerleri,
  comparison.py (paired/CI dokunulmadı), case-weighted ağırlık,
  `decision_accuracy` boş-küme `0.0` kuralı (bildirilen). Estimand,
  parent-eşit ağırlık, bootstrap varsayımı, boyut hedefleri seçilmedi.

## Değişen / yeni dosyalar

- `src/sloplab/scoring/metrics.py` (yalnızca değişen kaynak; 234 satır
  diff): validator, çift helper'ları, iki formül, coverage.
- Yeni testler (7): `tests/regression/test_metric_contracts.py`.
- Dokunulmayan: `comparison.py`, `writers.py`, mevcut testler.
- Belgeler: `metric-contracts.md` (sözleşme tablosu + eski/yeni tablosu).

## Test / doğrulama

- Karşıörnekler önce kırmızı doğrulandı (`-0.25`, `0.025`), düzeltmeyle
  yeşil (`0.0`, `0.475`).
- Hedefli küme: **231 passed**. Tam offline paket: **339 passed**
  (332 + 7). ruff check/format, mypy temiz. Sıfır canlı istek.

## Deterministik study

Yeni benzersiz kök `/tmp/sloplab-e4a-XLXWiE` (297 cases, 2 evaluators;
594 kayıt). E1e'ye göre: iki şema eki + iki düzeltilmiş türev
(`analysis.json`, `report.md`); ortak 478 hash IDENTICAL, kayıtlar ve
manifesto kimlikleri IDENTICAL. Susceptibility üretimde `0.0`lendi;
ECE/drift/accuracy aynı. `run-outputs.sha256` 484/484 doğrulandı. `/tmp`
kalıcı arşiv değildir.
