# E2b — Fiziksel istek bütçesi, retry/deadline ve tekrar kapsamı (teslim)

Durum: **E2b tamamlandı** (kabul ölçütleri karşılandı).
Tarih: 2026-09-09. Kök: `/home/kaan/sloplab`. Yürütücü: Luna.
Önkoşul: E2a kabul edildi (`../E2a-acceptance.md` — inceleyici `detail` sabit
kod düzeltmesi dahil); önceki değişiklikler korundu (`e2b.diff` kapsamı +
`logs/preserved-check.stdout.log`; E1a–E1e suites tam pakette yeşil).

## Davranış

- Tek bütçe sahibi: `CountingClient._reserve_or_raise` her fiziksel gönderim
  öncesi tek rezervasyon sınırıdır (doğrudan giriş dahil; cap aşılamaz).
  `set_deadline` zincire deadline taşır, sayaç sıfırlamaz.
- Retry politikası: parse/budget/deadline terminal (retry yok); timeout,
  transport ve açık 429/rate-limit retry eder. Sınıflandırma `failures.py`'de
  merkezi (`classify_dispatch_error`); detaylar sabit kod, exception metni
  kopyalanmaz. Adapter attempt (mantıksal) ile physical dispatch (sayaç) ayrı
  isimlerdedir.
- Deadline: `LLMBudget.deadline_s` (opsiyonel, default yok). Request timeout,
  monotonic run deadline, pacing ve Retry-After ayrı sözleşmelerdir. Sığmayan
  bekleme uyumadan reddedilir: başlamamış plan `not_run(deadline_exceeded)`,
  başlamış deneme `failed(deadline)`. Pilot dispatch-öncesi deadline kapısı da
  `not_run` üretir.
- Kapsam: planlanan birlik = seçili vakalar + evaluator + repeat.
  `check_outcome_coverage()` eksik/duplicate/yabancı/bozuk satırları bildirir;
  pilot kendi defterini doğrular (bozuklukta `OutcomeCoverageError` ile sesli
  başarısızlık). Stability tam başarı kapsamındaysa hesaplanır; manifestoda
  `coverage {expected, successful, complete}` + eksiklik nedeni görünür.
- Script ve doğrudan pilot aynı `run_llm_pilot` yolunu ve defter muhasebesini
  kullanır.

## Değişen / yeni dosyalar

- `failures.py` (E2a'dan yeni; bu tur genişletildi): `DeadlineExceeded`,
  `classify_dispatch_error`, `rate-limit`/`deadline` türleri.
- `adapter.py`: terminal-parse/budget/deadline, 429 sınıflandırması, deneme
  sayacı (ilk denemeden başlayan 1-tabanlı).
- `pilot.py`: rezervasyon kapısı, deadline donanımı/kapısı, nedenli not_run,
  coverage denetimi + `coverage` alanı, `PilotRunResult.coverage`.
- `config.py`: `LLMBudget.deadline_s` (opsiyonel).
- `base.py`: `evaluator_requires_labels()`; `oracle.py`: opt-in; rules/graph/llm:
  açık `False`. `harness.py`: capability-gated labels + failed guardı.
- `llm_bench.py`: defter-güdümlü stdout (NOT-RUN satırları eklendi).
- Testler: `test_budget_retry.py` (yeni, 7 test); adapter parse/budget attempt
  sayıları terminal politikaya çevrildi (açıkça değişen beklenti).
- E2b diff'i: `e2b.diff` (11 tracked dosya; `failures.py` zaten untracked E2a
  dosyasıydu, yeni test untracked listede).

## Test / doğrulama

- Yeni 7 + ilgili mevcut: 132 passed. Tam paket: 270 passed (263 + 7).
  ruff/format/mypy temiz. Sıfır canlı istek (fake transport + sahte saat).
- Yeni koşu (`/tmp/sloplab-e2a-u0PKCr/run`) vs E1e-review ref: 482 küme eşit,
  480 ham eşit (input-identity dahil), recipe semantic/location/metadata eşit,
  manifesto yalnız zamanlar; 297 vaka / 594 kayıt.

## E2b durumu ve kalanlar

**E2b tamamlandı.** E2'nin kapanma ölçüsü: outcome/karar ayrımı (E2a) +
bütçe/retry/deadline/coverage (E2b) kapandı. Kalanlar: eski bundle okuma/
migration ve ortak yayın koordinasyonu (**E3**); metrik formülleri (**E4**).
Deterministik-izolasyon geneli E3'ün koordinatörüne aittir (burada yapılmadı).
E2 bütünüyle kapanmadı; canlı pilot başlatılabilir ilan edilmedi.
