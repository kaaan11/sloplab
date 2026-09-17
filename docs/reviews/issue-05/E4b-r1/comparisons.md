# E4b-r1 — Karşılaştırma (comparisons.md)

## Referans ve yöntem

- Referans: `/tmp/sloplab-e1e-review-hoxabV/run` (son kabul çalışması).
- Yeni koşu: `/tmp/sloplab-e4b-r1-WI9ueE/run`, E4b-r1 koduyla CLI `study`
  ile üretildi (297 cases, 2 evaluators; 594 kayıt: canonical 120 +
  mutated 474). Eski yollar yeniden kullanılmadı.
- Yöntem: E0 rev3 yardımcısı değiştirilmeden çalıştırıldı.

## Ham farklar (bilinçli)

- Dosya kümesi: üç ek — `completion.json` (E3a),
  `materialization-ledger.jsonl` (E3b), `analysis-v1.json` (E4b; zarf
  şeması 2, outcomes yokluğu bağlı).
- Ortak kümede 2 dosya farklı: `analysis.json`, `report.md` (E4a formül
  düzeltmelerinin türevleri).
- Diğer 478 dosya IDENTICAL; `records.jsonl`, `suite-index.jsonl` (ham),
  manifesto kimlik alanları IDENTICAL (yalnız izinli zaman alanları).
- Tarihsel bacak (E1e↔E1e): IDENTICAL.

## Semantik farklar

- Yeni paket strict `complete` (485 dosya); sürümlü okuma OK (şema 2,
  coverage `planned=297/scored=297/failed=0/not_run=0`, outcomes yokluğu
  bağlı).
- Ham karar/hedef kayıtları değişmedi.

## Hüküm

E4b-r1, ham başarı verilerini değiştirmedi. Yardımcının `RESULT: FAIL`
çıktısı üç şema ekinden ve iki düzeltilmiş türev dosyadan ibarettir.
