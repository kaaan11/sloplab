# E1d — E0/yeni çalışma karşılaştırması

Yeni koşu: `/tmp/sloplab-e1d-jJOgHz/run` (E1d koduyla, 297 vaka, 2 evaluator).
Referans: `/tmp/sloplab-e0-zVHDyy/run-a` (E0, aynı config, aynı kök; mevcut).
Eski helper/allowlist değiştirilmedi.

## E0 rev3 helper (beklenen ret)

`logs/compare-e0-rev3.stdout.log` (exit 1): tam küme eşitliği `input-identity.json`
ekini reddetti (`only-in-b: input-identity.json`, `RESULT: FAIL`). Başka yeni/eksik
dosya yok.

## Faza özel helper (kabul)

`helpers/compare_e1d.py` (kaynağı teslimde), `logs/compare-e1d.stdout.log` (exit 0,
`RESULT: OK`):

| Kontrol | Sonuç |
| --- | --- |
| Dosya kümesi | Yalnız `input-identity.json` ek; eksik yok |
| Ortak 479 veri/index dosyası | Ham IDENTICAL (manifest hariç) |
| `manifest.json` | Yalnız `started_at`, `finished_at` farklı |
| Kimlik iç bağları | 297 satır 64-hex; selection/inputs yeniden hesabı OK; satır input_hash OK |
| Sıra/sayı | Kimlik sırası ilk evaluator kayıt sırasıyla aynı (297 vaka × 2 evaluator) |

Negatif kontrol (`logs/compare-e1d-neg.stdout.log`, exit 1): tek satır hash'i
oynanmış kopya `inputs_hash` + `input_hash` uyumsuzluğuyla reddedilir.

## Sayılar (ölçüldü)

- Vaka: 297 (60 canonical + 237 derived); evaluator kayıt satırı: 594.
- Yeni küme: 481 dosya (480 + `input-identity.json`); envanter `run-outputs.sha256`.
- Karar, hedef, vaka sayısı, metrik farkı: yok. Golden güncellenmedi.

Tam run dizini `/tmp/sloplab-e1d-jJOgHz/` içinde kalır (`run/`, `logs/`); `/tmp` kalıcı
arşiv değildir.
