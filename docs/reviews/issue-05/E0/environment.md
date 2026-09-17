# E0 ortam ve kimlik kaydı

## İncelenen kod, config, korpus ve ortam

- Çalışma kökü: `/home/kaan/sloplab`. Görev dosyası `docs/issue-05-E0-task.md`,
  üst plan `docs/issue-05-engineering-assessment-and-plan.md`,
  kaynak rapor `/home/kaan/GPT-Pro/reports/issue-05-Sloplab.report.md` (663 satır, bölüm bölüm okundu; tamamı bağlama yüklenmedi).
- `AGENTS.md`: repo kökünde **yok** (glob ile doğrulandı). Yerine `CONTRIBUTING.md`
  dışlandı; bu faz yalnız görev dosyasındaki kapsamı izledi. Alt dizin yönergesi:
  `docs/reviews/` bu görevde oluşturuldu (önceden yoktu); `docs/reviews/issue-05/E0/` ilk ve boş kardeş dizin olarak seçildi.
- Kaynak/config envanteri: `inventories/source-config-inventory-start.sha256` (32 dosya:
  pyproject, uv.lock, CI, reproducibility, study/runner/config, deterministic yaml,
  v1-core suite, CLI main, mutations textops/base/planner/materialize/evidence, parser,
  LLM adapter/pilot/script/prompt, scoring metrics/comparison/harness, models
  run/evaluation/enums/suite/manifest/report içinden ilgili olanlar, kaynak rapor, plan ve görev dosyası).
- Korpus: `inventories/corpus-canonical-inventory-start.sha256` (120 dosya; 60 fixture × report.md + manifest.yaml).
  Başlangıç/bitiş hash karşılaştırması: 120/120 eşit, uyumsuzluk 0
  (`inventories/corpus-canonical-inventory-end.sha256` + `end-verification.log`,
  üretim anı `2026-09-09T14:56:58Z` UTC — ölçüm anı, geçmişe tarihlendirme yok).
- Eski artefakt: `inventories/study-v02-inventory-start.sha256` (480 dosya). Eksik dosya yok.
  Bitiş envanteri `study-v02-inventory-end.sha256` ile bayt-bayt eşit (çalışmalar eski
  sonuçlara yazmadı). Kaynak/config için de `source-config-inventory-end.sha256`
  başlangıçla eşit. Üç `*-end` dosyası `helpers/make_inventories_e0.py` ile üretildi;
  yardımcının başlangıç dosyalarını bayt-bayt yeniden ürettiği
  `/tmp/sloplab-e0-zVHDyy/logs/inventory-verify-start.stdout.log` ile kanıtlı.
  `inputs-end.sha256` yalnız 2 config içerir; hükümsüzdür, korunur; yerini yukarıdaki
  eksiksiz `*-end` dosyaları alır.
- Yeni çıktılar: `inventories/run-a-outputs.sha256`, `inventories/run-b-outputs.sha256` (480'er dosya).
- Ek okunan dosyalar (doğrudan bağımlılık gerekçesiyle): `src/sloplab/models/suite.py`
  (B3 fallback), `src/sloplab/models/report.py` (U8 başlık kapsamı),
  `src/sloplab/mutations/operators/presentation.py` (U5/B10 uygunluk),
  `src/sloplab/evaluators/rules/baseline.py` (B6/U7),
  `src/sloplab/evaluators/rules/evidence_graph.py` (B7/U8),
  `tests/unit/test_evidence_graph_families.py` (B7),
  `tests/regression/test_suite_paths.py` + `tests/conftest.py` (test yan etkileri),
  `benchmarks/configs/smoke.yaml` + `experiments/configs/llm-pilot-v0.2.yaml` +
  `experiments/configs/llm-full-v0.2.yaml` (B3/B8/B12 retleri),
  `docs/evaluator-contract.md` (U6), `src/sloplab/models/manifest.py` (B4/B5/B11).

## Git durumu (başlangıç)

- HEAD: `9960f4fd517ff9ede511aebea0b7e2db9305819e` (branch `main`, detached değil).
- `git status --porcelain=v1` (başlangıç): ` M .gitignore`, untracked: `.claude/`,
  `arastirma.md`, `docs/issue-05-E0-task.md`, `docs/issue-05-engineering-assessment-and-plan.md`,
  `docs/reviews/` (bu görev), `muhendislik.md`. Staged diff yok.
- Dirty kapsamı: `.gitignore`'da tek satır ek (`gptpro-bundles/`); sonucu etkilemez.
  Untracked kaynak/config/girdi yok (listelenenler kullanıcı çalışması/belge).
- Eski manifest commit'i: `14547a00b306d0fcbbc8ada0326bd39787b03e5b`.
  Yerel commit nesnesi var (`git cat-file -t` → `commit`); HEAD'in atası
  (`merge-base --is-ancestor` true). Tag'ler yerelde mevcut; `v0.3.0` → `9960f4f`
  (mevcut HEAD). Tag yokluğu remote yokluğu kanıtlamaz (kontrol edilmedi).
  Eski commit'e checkout/çalıştırma yapılmadı.

## Ortam

- Sistem Python: `/usr/bin/python3`, `3.14.4`. Çalıştırma interpreter'ı
  (`uv run --offline --frozen`): `3.13.15`.
- Platform: `Linux … 6.18.33.2-microsoft-standard-WSL2 … x86_64`.
- `uv 0.12.5`. Paketler (çalıştırma ortamı): click `8.4.2`, pydantic `2.13.4`,
  pyyaml `6.0.3`, pytest `9.1.1`.
- `uv.lock` SHA-256: `4a4969aa…` (tam değer envanterde değil, logda: `logs/` yerine
  aşağıda — düzeltme: hash `4a4969aa2ced12163bfa5b16236a48fda93c6477ba52fdd81443bc84979ce8ab`),
  `pyproject.toml`: `249381c9cae85bf53e3baabb905e74356989e9ca35cc4789dbec36b3a8e1f63d`.
- Ağ kullanılmadı (`--offline --frozen`); kurulum/fetch/pull yok. Commit/push/branch değişimi yok.

## Dirty çalışma kapsamı

İzinli değişiklikler yalnız `docs/reviews/issue-05/E0/` altındadır
(raporlar, log referansları, envanterler, `helpers/compare_e0.py`).
`src/`, `tests/`, korpus, config, lock, `.gitignore`, eski sonuçlar ve mevcut
belgeler değiştirilmedi. Geçici çalışma verisi `/tmp/sloplab-e0-zVHDyy`
(`run-a/`, `run-b/`, `logs/`) — `/tmp` kalıcı arşiv değildir; inceleme bitene
kadar korunmalıdır.
