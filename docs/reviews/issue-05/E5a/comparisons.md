# E5a — Karşılaştırma (comparisons.md)

## Referans ve yöntem

- Referans: `/tmp/sloplab-e1e-review-hoxabV/run` (son kabul çalışması).
- Yeni koşu: `/tmp/sloplab-e5a-PTqVq6/run`, E5a koduyla CLI `study` ile
  üretildi (297 cases, 2 evaluators; 594 kayıt). Eski yollar yeniden
  kullanılmadı.
- Yöntem: E0 rev3 yardımcısı değiştirilmeden çalıştırıldı.
- Ek karakterizasyon: `benchmarks/suites/v1-core.yaml` + `corpus/`
  güncel kodla materyalize edilip committed paketle bayt-karşılaştırıldı
  (`test_materialize_matches_committed_bundle`).

## Ham farklar (bilinçli)

- Dosya kümesi: üç ek — `completion.json` (E3a),
  `materialization-ledger.jsonl` (E3b), `analysis-v1.json` (E4b).
- Ortak kümede 2 dosya farklı: `analysis.json`, `report.md` (E4a formül
  düzeltmelerinin türevleri; E5a ile ilgisiz, önceki paketlerden devralındı).
- Diğer 478 dosya IDENTICAL; `records.jsonl`, `suite-index.jsonl` (ham),
  manifesto kimlik alanları IDENTICAL (yalnız izinli zaman alanları).
- Tarihsel bacak (E1e↔E1e): IDENTICAL.

## Karakterizasyon karşılaştırması (türev baytları)

- 474 türev dosya committed paketle bayt-eşit; suite-index gövdesi eşit
  (başlıkta yalnız makine `corpus_root` farkı — E0-izinli).
- E5a çıktısında açıklanmayan türev bayt farkı: **sıfır**.

## Hüküm

E5a, üretim davranışını değiştirmedi (tek src eki: çağrılmayan
`span_authorized` yardımcısı). Yardımcının `RESULT: FAIL` çıktısı üç
şema ekinden ve iki devralınmış türev dosyadan ibarettir.
