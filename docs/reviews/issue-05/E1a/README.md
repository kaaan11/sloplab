# E1a — Deterministik study için erken ayar doğrulaması (teslim)

Durum: **E1a tamamlandı** (kabul ölçütleri karşılandı; E1'in tamamı kapanmadı).
Tarih: 2026-09-09. Çalışma kökü: `/home/kaan/sloplab`. Yürütücü: Luna.
Önkoşul: E0 kabul edildi, G0 geçti (`../E0-acceptance.md`).

## Değişen davranış

`run_deterministic_study` artık ilk satırda `preflight_study_config` çalıştırır;
desteklenmeyen ayar veya bilinmeyen evaluator adı varsa korpus üretimi, evaluator
çalıştırması ve çıktı yazımı başlamadan `StudyConfigError` (bir `ValueError` türü)
yükselir:

- nonempty `evaluators[i].config` → ret; hata evaluator adını ve
  `evaluators[i].config` alanını belirtir, ayar değerlerini mesaja dökmez.
- Bilinmeyen evaluator adı → ret; bütün adlar (son sıradaki dahil) çıktı üretiminden
  önce çözümlenir; registry mesajı (`unknown evaluator 'x'; registered: ...`) korunur.
- `analysis.paired_comparison=false`, `analysis.error_taxonomy=false` → ret.
- `provenance.record_commit_sha / record_suite_hash / record_evaluator_config_hash`
  alanlarından False olan → ilgili alan adıyla ret.
- Desteklenen girdiler değişmedi: boş config, kayıtlı evaluator adları (hard-code
  yok — registry ne kayıtlıysa o), `True` bayraklar, şema aralığındaki nondefault
  `bootstrap_resamples`/`bootstrap_ci`, farklı study/suite seed'leri.

CLI `study` komutu config hatalarını `ClickException` ile sunar (nonzero çıkış,
okunabilir mesaj, traceback yok). Beklenmeyen program hataları aynen yükselir
(geniş `except Exception` yok).

## Değişen dosyalar

- `src/sloplab/experiments/study.py` (+44): `StudyConfigError` + `preflight_study_config`;
  `run_deterministic_study` ilk satırda preflight çağırır. Seed/tahsis, metrik,
  evaluator formülleri, parser, materializer davranışı değişmedi.
- `src/sloplab/cli/main.py` (+12/-3): study komutunda `load_study_config`
  `ValueError` ve `StudyConfigError` için `ClickException` sınırı.
- `tests/regression/test_study_preflight.py` (yeni, 13 test): 6 parametreli ret,
  hata-içerik denetimi, sondaki bilinmeyen ad için çağrı-yokluğu (spy) + çıktı
  yokluğu, sentinel koruması (API+CLI), desteklenen ayarlar, CLI traceback yokluğu,
  CLI başarı yolu.
- Ek bağımlılık takibi yok (gerekmedi). AGENTS.md repo kökünde yok (E0'da da yoktu).

## Test / karşılaştırma sonuçları

- Yeni + ilgili mevcut testler: 20 passed
  (`test_study_preflight` 13, `test_experiments` 4, `test_cli` 3).
- Tam paket: 214 passed. ruff check, ruff format --check, mypy (değişen dosyalar): temiz.
- `commands.jsonl`: 16 gerçek komut (tam metin, cwd, exit, log). Ara iterasyonlar
  (exit 1'ler dahil) log-durumuyla açıkça kayıtlı; log'suz satırlar yeniden elde
  edilmiş sayılmıyor, kabul kanıtı log'lu koşular.
- E0 veri eşdeğerliği: yeni koşu (`/tmp/sloplab-e1a-ppqPYl/run`, 297 vaka) E0 `run-a`
  ile 480/480 dosya eşit; suite-index ham bayt eşit; manifesto yalnız zaman
  alanlarında farklı (E0 rev3 yardımcısı read-only, allowlist genişletilmedi).
  Karar/hedef/vaka/metrik farkı yok.

## Sınırlamalar ve E1'e kalanlar

- Preflight yalnız bu paketin ret listesini uygular; tarif kimliği, değişmez vaka
  girdisi, prompt bağı, hash şeması, LLM, metrik, atomiklik, bilimsel seçim E1'in
  sonraki paketlerinde.
- `StudyConfigError` yeni hata türüdür; doğrudan API çağıranlar `ValueError`
  yakalamaya devam edebilir. Registry `KeyError` metni korunur.

## Görev durumu

**E1a tamamlandı.** Kabul: retler yan etkiden önce (API+CLI), desteklenen ayarlar
gerilemedi, E0 çıktıları değişmedi. Sonraki pakete geçmeden Astra incelemesi bekleniyor.
