# E1e — E1d referanslı karşılaştırma

Yeni koşu: `/tmp/sloplab-e1e-w2dMaH/run` (E1e koduyla, 297 vaka, 2 evaluator).
Referans: `/tmp/sloplab-e1d-jJOgHz/run` (E1d, aynı config, aynı kök; mevcut).
Eski helper/allowlist değiştirilmedi.

## E0 rev3 helper (beklenen ret)

`logs/compare-e0-rev3.stdout.log` (exit 1): E0 `run-a` kümesine göre iki ek dosya
(`input-identity.json`, `execution-recipe.json`) → `RESULT: FAIL`. Başka yeni/eksik
dosya yok.

## Faza özel helper (kabul)

`helpers/compare_e1e.py` (kaynağı teslimde), `logs/compare-e1e.stdout.log` (exit 0,
`RESULT: OK`):

| Kontrol | Sonuç |
| --- | --- |
| Dosya kümesi | Yalnız `execution-recipe.json` ek; eksik yok |
| Ortak 480 dosya (manifest hariç) | Ham IDENTICAL (`input-identity.json` dahil) |
| `manifest.json` | Yalnız `started_at`, `finished_at` farklı |
| Tarif iç bağları | 7 hash yeniden hesabı OK; inputs/selection `input-identity.json` ile aynı |
| Sıra/sayı | Kimlik sırası ilk evaluator kayıt sırasıyla aynı (297 vaka × 2 evaluator) |

Negatif kontrol (`logs/compare-e1e-neg.stdout.log`, exit 1): analysis bölümü
oynanmış kopya `analysis_hash` uyumsuzluğuyla reddedilir.

## Sayılar (ölçüldü)

- Vaka: 297 (60 canonical + 237 derived); evaluator kayıt satırı: 594.
- Yeni küme: 482 dosya (481 + `execution-recipe.json`); envanter `run-outputs.sha256`.
- Karar, hedef, vaka sayısı, metrik farkı: yok. Golden güncellenmedi.

Tam run dizini `/tmp/sloplab-e1e-w2dMaH/` içinde kalır (`run/`, `logs/`); `/tmp` kalıcı
arşiv değildir.
