# E2a — Başarısız LLM yürütmesini karardan ayır, etiket erişimini sınırla (teslim)

Durum: **E2a tamamlandı** (kabul ölçütleri karşılandı).
Tarih: 2026-09-09. Kök: `/home/kaan/sloplab`. Yürütücü: Luna.
Önkoşul: E1 kapatıldı (`../E1e-acceptance.md`); önceki değişiklikler korundu
(`git diff --name-only` bu turda kapsam dışı tracked dosya eklemedi; dokunulmayan
2 dosya start==end doğrulandı; E1a–E1e suites tam pakette yeşil).

## Davranış

- `Evaluator.evaluate` başarıda `EvaluationResult` döndürmeye devam eder. Retry'lar
  bitince adapter typed `EvaluationFailure` yükseltir (karar/confidence/dimensions
  taşımaz): `error_kind` (parse/timeout/transport/budget), mantıksal
  `adapter_attempts` (fiziksel gönderim sayısı değildir), `rendered_prompt_hash`,
  kısa kontrollü `detail` (ham cevap/prompt/credential/yığın dökümü yok).
  `_failed_result` sentetik review üretimi kaldırıldı. Bütçe tükenmesi açık `budget`
  türüdür (transport değil). Success-path prompt hash'i ve frozen template korunur.
- `run_case`/pilot sınırında legacy `metadata.failed=True` sonucu başarı kaydına
  çevrilmez, `legacy` failure'a dönüşür. Eski arşiv kayıtları değiştirilmedi.
- Pilot defteri: başarılar `records.jsonl`'ye `CaseRecord`; her plan
  `(case_id, evaluator_name, repeat_index)` için `outcomes.jsonl` (`schema_version: 1`)
  satırı (`success`→record referansı, `failed`→tür/attempt/hash, kararsız;
  `not_run`→bütçe nedeni). Manifestoya `planned/successful/failed/not_run/scored`
  (`planned = s+f+n`, `scored = successful`) eklendi; request/error/timeout fiziksel
  sayaçlar korundu. `evaluations_attempted` = dispatched (success+failed), not_run
  hariç; records satır sayısına eşitlenmez.
- Stability yalnızca tam başarı kapsamındaysa hesaplanır; eksikte `{}` +
  `stability_omitted_reason` (`incomplete-success-coverage` /
  `single-repeat-or-empty`). Tam yoldaki değerler aynı fonksiyondan, değişmedi.
- Etiket yetkisi: `evaluator_requires_labels()` (default False); yalnız `oracle`
  (`requires_labels = True`) ground-truth kopyası alır, kararları aynı.
  Content evaluator'lar (rules/graph/llm dahil, açık `False`) boş labels görür.
  Pilot LLM'e `expected_decision` vermez (veri minimizasyonu, sandbox değil).
  R04 opaque-handle akışı aynı.

## Değişen / yeni dosyalar

- `src/sloplab/evaluators/llm/failures.py` (yeni): `EvaluationFailure`,
  `BudgetExhausted` (pilot'tan taşındı, pilot yeniden export eder),
  legacy-dönüşüm + sınır yardımcısı.
- `adapter.py`: raise-sözleşmesi, `_failed_result` silindi, parse/timeout/transport/
  budget ayrımı (200-karakter kontrollü detay).
- `base.py`: `evaluator_requires_labels()`; `oracle.py`: opt-in; rules/graph/llm:
  açık `False`.
- `harness.py`: capability-gated labels (çağrı-başı kopya) + failed-flag guardı.
- `pilot.py`: ledger döngüsü, `outcomes.jsonl`, manifesto sayıları/nedeni, coverage
  kapılı stability, boş-label pilot context'i, genişletilmiş `PilotRunResult`.
- `scripts/llm_bench.py`: defter-güdümlü stdout (aynı satır biçimi; FAILED-EVAL
  türüyle, NOT-RUN satırları eklendi).
- Testler: `test_outcomes_ledger.py` (yeni, 9 test); adapter/pilot/prompt
  failure-placeholder testleri yeni sözleşmeye çevrildi; E1b snapshot spy'larına
  (gerçekten etiket tüketen test double'ları) capability eklendi.
- E2a diff'i: `e2a.diff` (8 tracked dosya). Kapsam dışı bırakılanlar kapanışta.

## Test / doğrulama

- Yeni 9 + ilgili mevcut (adapter, pilot, script, prompt, snapshot, preflight,
  identity, recipe, experiments, CLI, remediation, pipeline): 124 passed.
  Tam paket: 262 passed. ruff/format/mypy temiz.
- Yeni koşu (`/tmp/sloplab-e2a-u0PKCr/run`) vs E1e-review ref: 482 küme eşit,
  480 ham eşit (input-identity dahil), execution-recipe semantic hash'leri +
  locations eşit, metadata eşit; manifesto yalnız zamanlar; 297 vaka / 594 kayıt.

## E2a durumu ve kalanlar (E2b/E3'e açık)

**E2a tamamlandı.** Kapanmayanlar: bütçe rezervasyon sahipliği, deadline/Retry-After
merkezileşmesi, tam tekrar-stabilitesi/coverage denetimi (**E2b**); eski bundle
okuma/migration, ortak yayın koordinatörü, deterministik-izolasyon geneli (**E3**);
metrik formülleri (**E4**). E2 bütünüyle kapanmadı; canlı pilot başlatılabilir
ilan edilmedi.
