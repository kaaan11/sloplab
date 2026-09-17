# E4a — Karşılaştırma (comparisons.md)

## Referans ve yöntem

- Referans: `/tmp/sloplab-e1e-review-hoxabV/run` (son kabul çalışması).
- Yeni koşu: `/tmp/sloplab-e4a-XLXWiE/run`, E4a koduyla CLI `study` ile
  üretildi (297 cases, 2 evaluators; 594 kayıt: canonical 120 + mutated
  474). Eski yollar yeniden kullanılmadı.
- Yöntem: E0 rev3 yardımcısı değiştirilmeden çalıştırıldı.

## Ham farklar (bilinçli)

- Dosya kümesi: yalnız `only-in-b: completion.json` (E3a) ve
  `only-in-b: materialization-ledger.jsonl` (E3b).
- Ortak kümede 2 dosya farklı: `analysis.json`, `report.md` (aşağıda).
  Diğer 478 dosya IDENTICAL.
- `records.jsonl`, `suite-index.jsonl` (ham), manifesto kimlik alanları:
  IDENTICAL (yalnız izinli zaman alanları farklı).
- Tarihsel bacak (E1e↔E1e): IDENTICAL.

## Semantik farklar (formül düzeltmesi)

- Susceptibility (paired): rules `-0.0189 → 0.0`, evidence-graph
  `0.0068 → 0.0`. Üretim verisindeki dengesiz çift dağılımının sahte
  nonzero değerleri silindi; çiftler toplu uyumlu.
- ECE/drift/accuracy: üretim verisinde değişmedi (karşıörnek Bin-9
  davranışı sentetik testle sabit: `0.025 → 0.475`).
- `analysis.json` paketlerine `metric_coverage` anahtarı eklendi
  (bilinçli şema eklemesi); ham karar/hedef kayıtları değişmedi.

## Hüküm

E4a, ham başarı verilerini değiştirmedi; yalnız düzeltilen metriklerin
türev çıktıları değişti. Yardımcının `RESULT: FAIL` çıktısı iki şema
ekinden ve iki düzeltilmiş türev dosyadan ibarettir.
