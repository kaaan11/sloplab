# E5b — Karşılaştırma (comparisons.md)

## Referans ve yöntem

- Referans: `/tmp/sloplab-e1e-review-hoxabV/run` (son kabul çalışması).
- Yeni koşu: `/tmp/sloplab-e5b-VbclxH/run`, E5b koduyla CLI `study` ile
  üretildi (297 cases, 2 evaluators; 594 kayıt). Eski yollar yeniden
  kullanılmadı.
- Yöntem: E0 rev3 yardımcısı değiştirilmeden çalıştırıldı.

## Ham farklar (bilinçli)

- Dosya kümesi: üç ek — `completion.json` (E3a),
  `materialization-ledger.jsonl` (E3b), `analysis-v1.json` (E4b).
- Ortak kümede 10 dosya farklı: 6 B1 dosyası (3 rapor + 3 manifesto —
  yukarıda) + `analysis.json`/`report.md` (E4a türevleri, devralındı) +
  `execution-recipe.json`/`input-identity.json` (değişen 3 girdinin
  türev hash'leri; vaka satırları yalnız 3 değişen vakada farklı,
  `selection_hash` eşit).
- Diğer 472 dosya IDENTICAL; `records.jsonl` kararları 594/594 aynı
  (0 flip); `suite-index.jsonl` ham IDENTICAL; manifesto kimlik
  alanları IDENTICAL (yalnız izinli zaman alanları).
- Tarihsel bacak (E1e↔E1e): IDENTICAL.

## Hüküm

E5b'nin ham farkları hedeflenen 3 vaka + türev hash'lerinden ibarettir.
Yardımcının `RESULT: FAIL` çıktısı üç şema ekinden, iki devralınmış
türevden ve B1 etki kümesinden ibarettir; açıklanmayan bayt farkı yoktur.
