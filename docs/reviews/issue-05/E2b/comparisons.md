# E2b — E1e-review referanslı karşılaştırma

Yeni koşu: `/tmp/sloplab-e2a-u0PKCr/run` (E2b koduyla, 297 vaka, 2 evaluator).
Referans: `/tmp/sloplab-e1e-review-hoxabV/run` (E1e kabul run'ı; mevcut).
Yöntem: E0 rev3 `helpers/compare_e0.py` (değişmeden) + recipe iç bağları.
Günlük: `logs/compare-e0.stdout.log` (exit 0, `RESULT: OK`; stderr boş).

## Sonuç

| Küme | ref vs yeni-run | Hüküm |
| --- | --- | --- |
| Dosya kümesi | 482 / 482 IDENTICAL | yeni/eksik dosya yok (ledger deterministik yola eklenmez) |
| Ham hash (480 dosya) | IDENTICAL | records, analysis, input-identity, execution-recipe dahil |
| `suite-index.jsonl` | ham bayt IDENTICAL | aynı kök |
| `manifest.json` | yalnız `started_at`, `finished_at` farklı | açıklanan zaman alanları |

Ham eşitlik: 480 veri/index dosyası (manifest hariç).

## Recipe iç bağları ve metadata (ayrı doğrulama)

- 7 semantic hash eşit: generation, evaluation, analysis, settings, inputs,
  selection, execution.
- `locations` eşit; `metadata` eşit (head `9960f4f…`, dirty `true`, CPython
  3.13.15, sloplab 0.2.2, lock `4a4969aa…`; dirty tam kod kimliği diye sunulmaz).
- Kayıt satırı: 594 (evaluator başına 297; canonical 120 + mutated 474).

Pilot failure çıktıları bilinçli protokol değişimidir; deterministik kayıtlarda
failure placeholder yoktu/yok, eski failure bayt eşitliği aranmadı.

Tam run dizini `/tmp/sloplab-e2a-u0PKCr/` içinde kalır (`run/`, `logs/`); `/tmp`
kalıcı arşiv değildir. Doğrulama sırasında `/tmp` dosyalarının paylaşımlı
makinede görünüp kaybolduğu gözlendi; kalıcı kanıt bu teslimdeki kopyalardır.
