# E0 — Referans ve bulgu doğrulama teslimi

- **Görev durumu: TAMAMLANDI.** Kritik matris, envanterler ve yapılabilen tüm kontroller teslim edildi.
- **G0 kapısı: GEÇTİ.** A/B ham-bayt eşit; girdi kayması yok; tarihsel farklar belgeli ve açıklanmış (yol/zaman/commit provenance ile sınırlı).
- HEAD: `9960f4fd517ff9ede511aebea0b7e2db9305819e` (`main`); eski manifest commit'i `14547a0…` yerelde var ve HEAD'in atası; `v0.3.0` HEAD'i gösterir.
- Ortam: sistem Python `3.14.4`, çalıştırma `3.13.15` (`uv --offline --frozen`), `uv 0.12.5`, click `8.4.2` / pydantic `2.13.4` / pyyaml `6.0.3` / pytest `9.1.1`.
- Sayılar (ölçüldü): **297 vaka** (60 canonical + 237 derived), **594 evaluator kayıt satırı** (evaluator başına 297). Eski/yeni/analiz değerleri `comparisons.md`'de.
- Kod düzeltmesi yapılmadı; E1'e geçilmedi. `src/`, `tests/`, korpus, config, lock, `.gitignore`, eski sonuçlar değişmedi (başlangıç/bitiş git durumu eşit).

## Ne çalıştırıldı

- İki yeni offline study (`run-a`, `run-b`, `/tmp/sloplab-e0-zVHDyy/`): ikisi de exit 0, `297 cases, 2 evaluators`. Config yalnız deterministik evaluator seçiyor (`rules-baseline`, `evidence-graph-baseline`); CLI `--out` yoluna yazıyor.
- A/B: `records.jsonl`, `suite-index.jsonl`, `analysis.json`, `report.md`, `results.csv` ham-bayt eşit; `adversarial/` 474/474 dosya eşit; `manifest.json`'da yalnız `started_at`/`finished_at` farklı (politika-uyumlu).
- Tarihsel (study-v02 vs run-a): kayıtlar, analiz, rapor, CSV ve türev ağacı ham-bayt eşit; `suite-index.jsonl` yalnız header `corpus_root` mutlak-yolunda farklı (gövde eşit); `manifest.json` 5 provenance alanında farklı (commit, yol, zamanlar, suite_hash). Farklar `comparisons.md` ve `helpers/compare_e0.py` çıktısında.
- Mevcut testler: `test_experiments.py` + `test_calibration_binning.py` + `test_suite_paths.py` → **10 passed**. Geçmeleri karşıörnek kapsamı anlamına gelmez (özellikle ECE karışık-bini kapsamaz).
- Mikro kontroller (bu tur çalıştırıldı): severity üyelik hatası + karışık-bin ECE düşmesi doğrulandı (`logs` `/tmp/.../microchecks.stdout.log`).

## Kritik bulgular (özet; tam matris `findings.md`)

- **B1 DOĞRULANDI** (kod + kayıtlı artefakt): üç örnekte devam satırı kalıntısı sürüyor; silici mekanizma güncel kodda aynı. Toplam etki E5'e.
- **B8/U1, failed-karar, cap/retry, U2/U9 DOĞRULANDI** (kod; ikisi bu tur çalıştırıldı): prompt-hash kopukluğu, failed→review karar sızıntısı, retry/bütçe sahipliği ayrımı (script preflight'ı yalnız scriptte), severity düşmesi (`"high"`→medium, `"HIGH"`→hata), türevlerin canonical yazılması, full-config/canonical-filtre çelişkisi.
- **B10/U4, U3, repeat DOĞRULANDI**: ağırlıklı susceptibility formülü + kayıtlı `+0.0067…` sinyali; karışık-bin `1.0` düşmesi (mevcut test kapsamaz); eksik repeat unanimous sayılabilir.
- **B11/U11, B12 DOĞRULANDI**: `correct` çift-tüketici riski + `compare`'in `metrics-*.json` okuması; atomik yayın yok + safety-blocked görünmezliği; study/generation seed ayrımı + uygulanmayan evaluator config'i.
- **Reddedilen teşhisler geçerli**: `:02d`, smoke fallback, CLI `max_cases=None` retleri güncel kodda da doğru.
- Kalan B2–B9 ve U5–U12 kısa durumlarla kapatıldı; hiçbiri sessizce kapatılmadı. U7/U8 mekanizma-doğrulandı, korpus etkisi BELİRSİZ.

## Engeller

Yok. Bağımlılık eksikliği, offline hazırlık başarısızlığı veya erişilemeyen kritik kanıt yok. `AGENTS.md` repo kökünde yok (kaydedildi); `SNAPSHOT.txt` export tarafı bu girişte erişilemez (U10'da ayrıldı).

## Önerilen sonraki dar iş

E1 (çözülmüş tarif + değişmez vaka girdisi): B2/B3/B8/B9/B11/B12'nin girdi-kimlik kısmı; U1/U6/U9 dahil. E2'nin outcome/bütçe ve E4'ün ölçüm işleri E1'in kimliklerine bağlanır. E5 (B1) ayrı üretim sürümüyle.

## Dosyalar

`comparison-policy.md` (önceden yazıldı), `comparisons.md`, `findings.md`,
`environment.md`, `commands.tsv`, `inventories/`, `helpers/compare_e0.py`,
`helpers/make_inventories_e0.py`, `helpers/microchecks_e0.py`.
Tam run çıktıları `/tmp/sloplab-e0-zVHDyy` (`run-a/`, `run-b/`, `logs/`) — inceleme bitene kadar korunsun; `/tmp` kalıcı arşiv değildir.

## İnceleme sonrası düzeltme notu (aynı gün, 2026-09-09)

- Bitiş envanteri eksiksizlendi: `source-config/corpus-canonical/study-v02` için
  `*-end.sha256` + `end-verification.log` (üçü de start ile eşit; ölçüm anı damgalı).
  `inputs-end.sha256` dar kapsamlıdır, hükümsüzdür.
- `compare_e0.py` rev3: 480 dosyalık tam küme denetimi; tarihsel allowlist-dışı fark
  çıkış kodunu bozar; suite-index A/B ham bayt zorunlu, tarihsel gövde ham bayt
  (LF/CRLF reddi negatif testlerle kanıtlı, mevcut artefaktlar geçer).
- `commands.tsv` tüm komutların gerçek metnini taşır; mikro kontroller
  `helpers/microchecks_e0.py` olarak teslimde, yeniden çalıştırma çıktısı birebir eşit.
