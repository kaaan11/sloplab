# E4b — Karşılaştırma (comparisons.md)

## Referans ve yöntem

- Referans: `/tmp/sloplab-e1e-review-hoxabV/run` (son kabul çalışması).
- Yeni koşu: `/tmp/sloplab-e4b-R3wpUI/run`, E4b koduyla CLI `study` ile
  üretildi (297 cases, 2 evaluators; 594 kayıt: canonical 120 + mutated
  474). Eski yollar yeniden kullanılmadı.
- Yöntem: E0 rev3 yardımcısı değiştirilmeden çalıştırıldı.

## Ham farklar (bilinçli)

- Dosya kümesi: üç ek — `completion.json` (E3a),
  `materialization-ledger.jsonl` (E3b), `analysis-v1.json` (E4b, ayrı
  ad/sürüm; `analysis.json` aynen korunur).
- Ortak kümede 2 dosya farklı: `analysis.json`, `report.md` (E4a formül
  düzeltmelerinin türevleri; ayrıntı E4a karşılaştırmasında).
- Diğer 478 dosya IDENTICAL; `records.jsonl`, `suite-index.jsonl` (ham),
  manifesto kimlik alanları IDENTICAL (yalnız izinli zaman alanları).
- Tarihsel bacak (E1e↔E1e): IDENTICAL.

## Semantik farklar

- Yeni paket strict `complete` (484 dosya); `analysis-v1.json` doğrulanmış
  okumadan geçer (sürüm 1, kayıt hash bağı + coverage tutarlı).
- Ham karar/hedef kayıtları değişmedi; metrik formül farkları E4a
  kapsamındadır.

## Hüküm

E4b, ham başarı verilerini ve E4a metrik değerlerini değiştirmedi;
yalnız sürümlü analiz ekledi. Yardımcının `RESULT: FAIL` çıktısı üç
şema ekinden ve iki düzeltilmiş türev dosyadan ibarettir.
