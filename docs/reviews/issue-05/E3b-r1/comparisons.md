# E3b-r1 — Karşılaştırma (comparisons.md)

## Referans ve yöntem

- Referans: `/tmp/sloplab-e1e-review-hoxabV/run` (son kabul çalışması).
- Yeni koşu: `/tmp/sloplab-e3b-r1-Rs1HvD/run`, E3b-r1 koduyla CLI `study`
  ile üretildi (297 cases, 2 evaluators; 594 kayıt: canonical 120 +
  mutated 474). Eski yollar yeniden kullanılmadı.
- Yöntem: E0 rev3 yardımcısı değiştirilmeden çalıştırıldı.

## Ham farklar (iki bilinçli ek)

- Dosya kümesi: yalnız `only-in-b: completion.json` (E3a işareti) ve
  `only-in-b: materialization-ledger.jsonl` (E3b defteri). Başka ek/eksik
  yok; `publish-in-progress.json` artığı yok (`finish_publish` kaldırdı).
- Ortak küme hash: 480/480 IDENTICAL.
- `suite-index.jsonl` ham bayt IDENTICAL.
- `manifest.json` farklı alanlar: yalnız izinli zaman alanları.
- Tarihsel bacak (E1e↔E1e): IDENTICAL.

## Semantik farklar

- Yeni paket strict reader ile doğrulanır (`complete`, 483 dosya).
- Yardımcının `RESULT: FAIL` çıktısı iki bilinçli ekten ibarettir.

## Hüküm

E3b-r1, study içeriğini değiştirmedi (iki ek dosya hariç ham + semantik
OK). E0/E1 deterministik başarı verileri açıklanmayan biçimde değişmedi.
