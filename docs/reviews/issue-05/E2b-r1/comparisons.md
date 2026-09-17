# E2b-r1 — Karşılaştırma (comparisons.md)

## Referans ve yöntem

- Referans: `/tmp/sloplab-e1e-review-hoxabV/run` (E1e kabul çalışması; E2b'nin
  de karşılaştırdığı son kabul referansı).
- Yeni koşu: `/tmp/sloplab-e2b-r1-8Z7OOZ/run`, E2b-r1 koduyla
  `sloplab study experiments/configs/deterministic-study-v0.2.yaml --out`
  ile üretildi (297 cases, 2 evaluators). E2a yolu
  (`/tmp/sloplab-e2a-u0PKCr/run`) yeniden kullanılmadı; üzerine yazılmadı.
- Yöntem: E0 rev3 yardımcısı `docs/reviews/issue-05/E0/helpers/compare_e0.py`
  değiştirilmeden çalıştırıldı (E1e-run ↔ R1-run, tarihsel üçüncü sütun E1e).

## Ham farklar

- Dosya kümesi: 482/482 IDENTICAL.
- Ham hash: 480/480 IDENTICAL (`manifest.json` + `suite-index.jsonl` atlandı).
- `suite-index.jsonl` ham bayt IDENTICAL.
- `manifest.json` farklı alanlar: yalnız `started_at` / `finished_at`
  (izinli zaman alanları).

## Semantik farklar

- 7 recipe hash eşit; `locations` eşit; `metadata` eşit (E2b ile aynı tablo).
- Kayıt sayıları: toplam 594 (`records.jsonl`: canonical 120 + mutated 474;
  E2b teslimindeki yapıyla aynı).
- Bilinçli şema farkı (study çıktısını ETKİLEMEZ, yalnız LLM pilot
  manifestolarını etkiler): `counters.requests` → `counters.physical_dispatches`.
  Deterministik study evaluator'ları kural/oracle tabanlı olduğundan bu
  anahtar study çıktılarında yoktur; ham eşitlik bunu doğrular.

## Hüküm

E2b-r1, deterministik study davranışını değiştirmedi (ham + semantik OK).
Sayfa-dışı tek fark çalıştırma zaman damgalarıdır. Provenance doğrudur:
benzersiz R1 kökü, R1 adlandırması, E2a yolunun yeniden kullanımı yok.
