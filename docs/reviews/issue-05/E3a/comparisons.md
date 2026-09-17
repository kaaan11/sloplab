# E3a — Karşılaştırma (comparisons.md)

## Referans ve yöntem

- Referans: `/tmp/sloplab-e1e-review-hoxabV/run` (son kabul çalışması).
- Yeni koşu: `/tmp/sloplab-e3a-EPC7GP/run`, E3a koduyla CLI `study` ile
  üretildi (297 cases, 2 evaluators). E1e/E2a/E2b-r2 yolları yeniden
  kullanılmadı.
- Yöntem: E0 rev3 yardımcısı değiştirilmeden çalıştırıldı. Yardımcı yeni
  şema dosyasını bilmediği için küme farkını raporlar (aşağıda); ham
  eşitlik ayrıca doğrulanır.

## Ham farklar (bilinçli tek ek)

- Dosya kümesi: tek fark `only-in-b: completion.json` (yeni şema işareti).
  Başka ek/eksik yok.
- Ortak küme hash: 480/480 IDENTICAL (`manifest.json` + `suite-index.jsonl`
  atlandı).
- `suite-index.jsonl` ham bayt IDENTICAL.
- `manifest.json` farklı alanlar: yalnız izinli zaman alanları (E3a
  manifestoya alan eklemez).
- Tarihsel bacak (E1e↔E1e): IDENTICAL.

## Semantik farklar

- Kayıt yapısı E2b-r2 ile aynı (toplam 594; aşağıda envanter).
- Yeni bundle strict reader ile doğrulanır: `verify_bundle(kind="study")`
  OK (482 dosya); `classify` → `"complete"`. E1e referansı `"legacy"`
  olarak tanınır ve strict reader tarafından reddedilir.
- Şema farkı: yalnız `completion.json` eklenmesi (deterministik belge;
  zaman damgası yok). Legacy dönüştürme yoktur.

## Hüküm

E3a, study içeriğini değiştirmedi (işaret hariç ham + semantik OK).
Karşılaştırma yardımcısının `RESULT: FAIL` çıktısı, bilinçli tek dosya
eklemesinden ibarettir; yardımcının kendisi değiştirilmedi.
