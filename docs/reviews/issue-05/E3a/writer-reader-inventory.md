# E3a — Yazıcı/okuyucu envanteri (writer-reader-inventory.md)

## Yazıcılar (sahiplik)

| Yazar | Yazdıkları | Paket | İşaret |
| --- | --- | --- | --- |
| `run_deterministic_study` (`experiments/study.py`) | `suite-index.jsonl`, `adversarial/` ağaçları, `input-identity.json`, `execution-recipe.json`, `records.jsonl`, `manifest.json` | study (kısmi — kütüphane adımı, publish sınırı değil) | YOK (çıktısı strict reader'da legacy biçimli görünür) |
| CLI `study` (`cli/main.py`) | `analysis.json`, `results.csv`, `report.md` + `completion.json` | study (tam publish) | VAR (`study`) |
| `run_llm_pilot` (`experiments/pilot.py`) | `records.jsonl`, `outcomes.jsonl`, `manifest.json` + `completion.json` | llm-pilot (tam publish) | VAR (`llm-pilot`) |
| `scripts/llm_bench.py` | `records.jsonl` kopyasını `args.out`'a taşır (paket dışı türev) | — (tüketici kopyası) | YOK |
| `materialize_suite` (`mutations/materialize.py`) | `suite-index.jsonl` + `adversarial/` ağaçları (girdi üretimi) | study paketinin girdisi | YOK (bütünlük alt akışta: `suite_hash` + completion haritası) |
| CLI `evaluate`/`benchmark` (`_run_evaluators_over_suite` + rapor) | `run.jsonl`, `metrics-*.json`, `report.md` (+`results.csv`, +materyalize girdiler) | LEGACY paket | YOK (tanınır, dönüştürülmez) |

## Okuyucular

| Okuyucu | Okudukları | Şema |
| --- | --- | --- |
| `verify_bundle` / `classify_bundle` (`experiments/bundle.py`) | `completion.json` + tam dosya kümesi | YENİ strict sınır |
| CLI `compare` | `metrics-*.json` | legacy (değişmedi) |
| CLI `report` | `run.jsonl` | legacy (değişmedi) |
| CLI `study` / `benchmark` iç okuma (`read_run_jsonl`) | `records.jsonl` / `run.jsonl` | kendi yazdığı çıktı (değişmedi) |
| `read_suite_index`, `build_cases` (`scoring/harness.py`) | `suite-index.jsonl` | girdi (değişmedi) |
| `compare_e0.py` (E0 yardımcısı, dondurulmuş) | tam run ağacı | referans karşılaştırma (değişmedi) |
| `test_doc_consistency`, remediation testleri | `benchmarks/results/v1-core-example` (committed) | legacy referans (değişmedi) |
| E2 serisi ledger/coverage testleri | pilot `records`/`outcomes`/`manifest` (doğrudan) | yeni paket dosyaları (işaretsiz okuma sürer) |

## Önbellek notu ("cache edilmiş analiz")

Kodda yazmalı analiz önbelleği yoktur: CLI `study` her koşuda
`analysis.json`'u yeniden hesaplar. Önbellek rolündeki eserler şunlardır ve
yalnızca okunur: committed `benchmarks/results/v1-core-example` paketi,
`/tmp` altındaki review koşuları ve E0/E2 teslim hash envanterleri. Tümü
legacy olarak tanınır; strict reader reddeder.

## Sınır kararları

- `run_deterministic_study` işaret yazmaz: publish sınırı CLI `study`'dir.
  Doğrudan koşucu çıktısı eksik paket değil, "henüz yayımlanmamış ara
  çıktı"dır (strict reader reddeder; testle sabit).
- `evaluate`/`benchmark` paketleri yeni şemaya taşınmadı: `run.jsonl` başlığı
  duvar-saati taşır, içerik-hash işareti stabil olmaz; legacy olarak tanınır
  (E3b kapsamı).
- Mevcut okuyucuların hiçbiri strict reader'a geçirilmedi (tüketici geçişi
  E3b); davranışları değişmedi.
