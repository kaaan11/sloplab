# E2b-r2 — Karşılaştırma (comparisons.md)

## Referans ve yöntem

- Referans: `/tmp/sloplab-e1e-review-hoxabV/run` (son kabul çalışması).
- Yeni koşu: `/tmp/sloplab-e2b-r2-PnuvGm/run`, E2b-r2 koduyla
  `sloplab study experiments/configs/deterministic-study-v0.2.yaml --out`
  ile üretildi (297 cases, 2 evaluators). E1e/E2a yolları yeniden
  kullanılmadı; üzerine yazılmadı.
- Yöntem: E0 rev3 yardımcısı `docs/reviews/issue-05/E0/helpers/compare_e0.py`
  değiştirilmeden çalıştırıldı.

## Ham farklar

- Dosya kümesi: 482/482 IDENTICAL.
- Ham hash: 480/480 IDENTICAL (`manifest.json` + `suite-index.jsonl` atlandı).
- `suite-index.jsonl` ham bayt IDENTICAL.
- `manifest.json` farklı alanlar: yalnız `started_at` / `finished_at`
  (izinli zaman alanları).

## Semantik farklar

- 7 recipe hash eşit; `locations` eşit; `metadata` eşit.
- Kayıt sayıları: toplam 594 (`records.jsonl`: canonical 120 + mutated 474;
  E2b/E2b-r1 yapısıyla aynı).
- Şema farkı yok: study çıktıları E2b-r1 ile aynı anahtarları taşır
  (LLM pilot sayacı study yolunda yoktur).

## Hüküm

E2b-r2, deterministik study davranışını değiştirmedi (ham + semantik OK).
Sayfa-dışı tek fark çalıştırma zaman damgalarıdır. Provenance doğrudur:
benzersiz R2 kökü, R2 adlandırması.
