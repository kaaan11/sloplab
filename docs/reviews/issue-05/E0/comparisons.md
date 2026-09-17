# E0 karşılaştırma sonuçları (A/B ve tarihsel)

Politika: `comparison-policy.md` (çıktılar görülmeden yazıldı).
Yardımcı: `helpers/compare_e0.py` rev3 (tüm 480 dosyalık küme + tarihsel allowlist
çıkış kodunda; suite-index A/B ham bayt zorunlu, tarihsel gövde ham bayt).
Yeniden çalıştırma: `/tmp/sloplab-e0-zVHDyy/logs/compare-rev3.stdout.log`
(`RESULT: OK`, exit 0). İlk çalıştırma günlükleri `compare-helper.stdout.log` ve
`compare-helper-rerun.stdout.log` korunur. Negatif kanıt: CRLF'li suite-index A/B'de
(`compare-neg-ab.stdout.log`, exit 1) ve tarihsel gövdede (`compare-neg-hist.stdout.log`,
exit 1) reddedilir; mevcut artefaktlar rev3 altında geçer.
Çalışma kökü: `/tmp/sloplab-e0-zVHDyy` (`run-a/`, `run-b/`, `logs/`).
Ham hash listeleri: `inventories/run-a-outputs.sha256`, `inventories/run-b-outputs.sha256`,
`inventories/study-v02-inventory-start.sha256`.

## Sayı sözlüğü (ölçüldü, hard-code değil)

- Vaka sayısı (suite): **297** (`study` çıktısı: `297 cases, 2 evaluators`; suite-index
  gövdesi: 60 canonical + 237 mutated + 1 header = 298 satır).
- Evaluator kayıt satırı: **594** (`records.jsonl` satır sayısı; evaluator başına 297:
  rules-baseline 297, evidence-graph-baseline 297; tür kırılımı toplamda canonical 120 + mutated 474).
- Kaynak raporun 297'si vaka sayısıdır; kayıt satırı sayısı değildir. Bu ayrım korundu.

## A/B (run-a vs run-b) — GEÇTİ

| Dosya/küme | Sonuç | Değer |
| --- | --- | --- |
| `records.jsonl` | Ham bayt eşit | `25dcc0c806da…` / `25dcc0c806da…` |
| `suite-index.jsonl` | Ham bayt eşit | `c83150c8b4c7…` |
| `analysis.json` | Ham bayt eşit | `2452d7110959…` |
| `report.md` | Ham bayt eşit | `98d3c50ab834…` |
| `results.csv` | Ham bayt eşit | `c56655f3d81c…` |
| `adversarial/` | Göreli küme + ham hash eşit | 474 / 474 dosya |
| `manifest.json` | Ham fark yalnız değişken alanlarda | `started_at`, `finished_at` farklı; diğer tüm alanlar eşit |

Girdi kayması yok: config hash'leri başlangıç/bitiş eşit
(`deterministic-study-v0.2.yaml e24a7047…`, `v1-core.yaml 95a68b1c…`),
corpus 120 dosya başlangıç/bitiş eşit (uyumsuzluk 0).
A/B'de dosya, vaka, evaluator ve alan düzeyinde açıklanmayan fark **0**.

## Tarihsel (study-v02 vs run-a) — farklar belgeli ve açıklanmış

| Dosya/küme | Sonuç | Açıklama |
| --- | --- | --- |
| `records.jsonl` | Ham bayt EŞİT | 594 satır, evaluator kırılımı eşit |
| `analysis.json` | Ham bayt EŞİT | `bundles` dahil tam eşit (`analysis identical: True`, paired eşit) |
| `report.md` | Ham bayt EŞİT | — |
| `results.csv` | Ham bayt EŞİT | — |
| `adversarial/` | Göreli küme + ham hash EŞİT | 474 / 474 dosya |
| `suite-index.jsonl` | Ham FARKLI (tek satır) | Yalnız 1. satır (header `corpus_root`): eski `/home/kaan/ai-workspaces/sloplab/corpus` → yeni `/home/kaan/sloplab/corpus`. 2+ satırlar bayt-bayt eşit |
| `manifest.json` | Ham FARKLI (5 alan) | `commit_sha` (`14547a0…` → `9960f4f…`), `corpus_root` (yukarıdaki yol), `started_at`/`finished_at`, `suite_hash` (`e64565c0…` → `c83150c8…`; suite_hash index dosyasının hash'i olduğu için header yol farkını yansıtır). `config_hash`, evaluator hash'leri, seed, evaluator listesi eşit |

Kayıtlı metrik değerleri (eski = yeni, `analysis.json` bundles):
- evidence-graph-baseline: accuracy `0.5420875420875421`, MDR `0.125` (96'da), drift `0.0`,
  susceptibility `+0.006787330316742085`, ECE `0.27011784511784503`.
- rules-baseline: accuracy `0.8114478114478114`, MDR `0.8020833333333334`,
  drift `0.0070921985815602835`, susceptibility `-0.018853695324283576`,
  ECE `0.2977744107744108`.

## Yorum sınırları

- Eski/yeni `records.jsonl` eşitliği, eski commit'in kendi ortamında yeniden
  üretildiği anlamına gelmez (bu fazda eski commit checkout/çalıştırma yapılmadı).
- Normalize (yol/zaman maskeli) eşitlik ayrıca hesaplanmadı; ham eşitlik tablosu
  yukarıdadır, maskeleme ham eşitlik diye sunulmuyor.
- Beklenmeyen yeni/eksik dosya yok: run-a, run-b ve study-v02'nin üçü de 480 dosya
  (474 adversarial + 6 üst düzey).
