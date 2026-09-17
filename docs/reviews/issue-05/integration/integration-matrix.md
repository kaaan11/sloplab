# Bütünleşik kapanış — sözleşme matrisi (integration-matrix.md)

Her satır: sözleşme → doğrulayan dosya/komut → gözlenen sonuç (bu teslimde).

## E0 — Girdi kimliği ve determinizm

| Sözleşme | Doğrulama | Sonuç |
| --- | --- | --- |
| Aynı girdi aynı baytları üretir | İki run karşılaştırması (`diff-policy.md` + run-a/b SHA-256) | Politika-dışı fark 0 (yalnız izinli zaman + manifest hash girdisi) |
| Tarihsel artefakt değişmezliği | `git diff --stat` (benchmarks, corpus, E0–E5b-r1 kanıtları) | 0 fark |

## E1 — Tarif, kimlik, seçim birliği

| Sözleşme | Doğrulama | Sonuç |
| --- | --- | --- |
| suite_hash girdiyi bağlar | Zincir betiği: `manifest.suite_hash == sha256(suite-index.jsonl)` | PASS (run A) |
| 297 vaka + başlık | suite-index satır sayımı | 298 satır (başlık + 297) |
| planned union | Okuyucu vaka kümesi == index kümesi (evaluator başına) | PASS (v1 okuma içinde) |

## E2 — Outcome, bütçe, retry, coverage

| Sözleşme | Doğrulama | Sonuç |
| --- | --- | --- |
| Tek bütçe sahibi + exact sayaçlar | Fake-transport pilot koşusu (ok/not-ok) + `verify_bundle` | PASS; `physical_dispatches` exact |
| failed outcome puanlanmaz | `compute_metrics` kayıtları + coverage | failed=1 → scored=0, coverage görünür |
| Ledger/kapsama uzlaşması | Pilot manifestosu + outcomes defteri | planned == scored + failed + not_run |

## E3 — Bundle, publish, legacy

| Sözleşme | Doğrulama | Sonuç |
| --- | --- | --- |
| Marker-son yayın + strict okuma | `verify_bundle` (iki run) | `complete` |
| Kesik/karışık/stale reddi | Negatif fixture'lar (kesik: marker-sl; karışık: crafted kayıt; stale: crafted coverage) | Üçü de `AnalysisError`/`BundleError` |
| Legacy açık mod | Committed örnek compare/report | `note:` ile okunur, yazılmaz |
| Yeniden-yazım yarışı | begin-önce/in-progress-önce sırası | publish testleriyle sabit (paket yeşil) |

## E4 — Metrikler ve sürümlü analiz

| Sözleşme | Doğrulama | Sonuç |
| --- | --- | --- |
| Paired susceptibility / kapalı-bin ECE | Karşıörnek testleri + E1e yeniden hesap | `0.0` / `0.475`; üretimde sahte nonzero yok |
| Kayıt tekilliği/correct/failed/parent | `validate_metric_records` (her `compute_metrics` girişi) | Committed 594 kayıt OK |
| Sürüm bağı (şema 2 / tanım 1) | `read_versioned_analysis` + coverage/metrik yeniden doğrulama | PASS; sahte coverage/metrik reddedildi |
| Coverage denklemleri | Zarf `planned == scored + failed + not_run` (yayın + okuma) | PASS (297 = 297 + 0 + 0) |

## E5 — Kaynak aralığı ve üretim sürümü

| Sözleşme | Doğrulama | Sonuç |
| --- | --- | --- |
| Tam-öğe aralığı + komşu koruma | 3 rapor diff'i (yalnız `-` kalıntı) + 474−6 bayt-eşit | PASS |
| Zorunlu identity + stale ret | Karşıörnek iki yolda + 11 çağrı noktası denetimi | Hepsi `StaleSpanError`/`TypeError` |
| `full-item-v1` kimliği ayrı | Defter başlığı + 3 vaka manifestosu; paket sürümü `0.2.2` sabit | PASS |
| 0 flip / metrik-nötrlük | Eski×yeni kayıt (594=594) + tanım-sabit metrik karşılaştırma | 0 flip; metrikler birebir |

## Bilerek çalıştırılmayan hücre

- llm-pilot canlı değerlendirmesi (canlı API gerektirir): sunulmuyor;
  pilot sözleşmeleri fake-transport koşusuyla doğrulandı.
