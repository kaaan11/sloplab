# E3b — Karşılaştırma (comparisons.md)

## Referans ve yöntem

- Referans: `/tmp/sloplab-e1e-review-hoxabV/run` (son kabul çalışması).
- Yeni koşu: `/tmp/sloplab-e3b-gHUSfs/run`, E3b koduyla CLI `study` ile
  üretildi (297 cases, 2 evaluators; 594 kayıt: canonical 120 + mutated
  474). Eski yollar yeniden kullanılmadı.
- Yöntem: E0 rev3 yardımcısı değiştirilmeden çalıştırıldı.

## Ham farklar (iki bilinçli ek)

- Dosya kümesi: yalnız `only-in-b: completion.json` (E3a işareti) ve
  `only-in-b: materialization-ledger.jsonl` (E3b defteri). Başka ek/eksik yok.
- Ortak küme hash: 480/480 IDENTICAL.
- `suite-index.jsonl` ham bayt IDENTICAL.
- `manifest.json` farklı alanlar: yalnız izinli zaman alanları (E3b
  study manifestosuna alan eklemez).
- Tarihsel bacak (E1e↔E1e): IDENTICAL.

## Semantik farklar

- Ledger uzlaşması (yeni koşu): planned 280 = written 237 + no_op 43;
  selected 297 = written 237 + canonical 60; kayıtlar 594 = 120 + 237×2.
  43 no-op daha önce sessiz `skipped` satırlarıydı; şimdi defterde görünür.
- Yeni paket strict reader ile doğrulanır (`complete`, 483 dosya).
- Yardımcının `RESULT: FAIL` çıktısı iki bilinçli ekten ibarettir.

## Hüküm

E3b, study içeriğini değiştirmedi (iki ek dosya hariç ham + semantik OK).
E0/E1 deterministik başarı verileri açıklanmayan biçimde değişmedi.
