# E5b-r1 — Karşılaştırma (comparisons.md)

## Referans ve yöntem

- Referans: `/tmp/sloplab-e1e-review-hoxabV/run` (son kabul çalışması).
- Yeni koşu: `/tmp/sloplab-e5b-r1-OcoEUQ/run`, E5b-r1 koduyla CLI `study`
  ile üretildi (297 cases, 2 evaluators; 594 kayıt). Eski yollar yeniden
  kullanılmadı.
- Yöntem: E0 rev3 yardımcısı değiştirilmeden çalıştırıldı.

## Ham farklar (bilinçli)

- Dosya kümesi: üç ek — `completion.json` (E3a),
  `materialization-ledger.jsonl` (E3b), `analysis-v1.json` (E4b).
- Ortak kümede 10 dosya farklı: 6 B1 dosyası (3 rapor kalıntı-satır
  silme + 3 manifesto kimliği) + `analysis.json`/`report.md` (E4a
  türevleri, devralındı) + `execution-recipe.json`/`input-identity.json`
  (değişen 3 girdinin türev hash'leri; vaka satırları yalnız 3 değişen
  vakada farklı).
- Diğer 472 dosya IDENTICAL; `records.jsonl` kararları 594/594 aynı
  (0 flip); `suite-index.jsonl` ham IDENTICAL; manifesto kimlik
  alanları IDENTICAL (yalnız izinli zaman alanları).
- B1 türev baytları E5b koşusuyla birebir aynı (düzeltme korunur).
- Tarihsel bacak (E1e↔E1e): IDENTICAL.

## Hüküm

E5b-r1 ham farkları E5b etki kümesiyle aynıdır. Yardımcının `RESULT:
FAIL` çıktısı üç şema ekinden, iki devralınmış türevden ve B1 etki
kümesinden ibarettir; açıklanmayan bayt farkı yoktur.
