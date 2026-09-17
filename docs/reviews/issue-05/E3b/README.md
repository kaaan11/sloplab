# E3b — Legacy okuma, materialization defteri ve kontrollü yayın

Önkoşul: [E3a kabulü](../E3a-acceptance.md) (inceleyici düzeltmeli).
Ortak kurallar: [worker teslim protokolü](../../issue-05-worker-delivery-protocol.md).
Önceki kanıtlar değiştirilmedi. E3 kapanmadı; canlı pilot ilan edilmedi.

## Uygulanan davranış

- Okuyucu sınırı: `open_result_dir` (complete → doğrula+oku; legacy →
  açık legacy mod + stderr notu; bozuk/tanınmayan → `BundleError`).
  Bağlananlar: CLI `compare`, CLI `report`, benchmark/STUDY iç okumaları,
  `llm_bench` pilot tüketimi (doğrulanmazsa çıkış 1 — kontrollü yayın).
  Bypass regression testleri (`test_reader_boundary.py`).
- Legacy: committed örnek + E3a-öncesi `/tmp` koşuları + işaretsiz ara
  çıktılar `legacy` tanınır; strict reader reddeder; tarihsel dosya
  yazılmaz, dönüştürme yok. Yazmalı analiz önbelleği kodda yoktur
  (analysis her koşuda yeniden hesaplanır); önbellek rolündeki okumalar
  aynı kapıdan geçer.
- Materialization defteri (`materialization-ledger.jsonl`): her plan tam
  bir kez `written`/`no_op`/`duplicate`/`safety_blocked`/`error`;
  plan hatası kardeşleri durdurmaz; safety detayı ham metin taşımaz; hata
  detayı `<Tür> in <aşama>` kalıbındadır. `read_materialization_ledger`
  iç denkliği, `check_materialization` defter↔indeks denkliğini doğrular
  (`planned == w+no+d+s+e`; `selected == written + canonical`).
- İzolasyon: `run_suite_with_outcomes` yalnız `EvaluationFailure`'ı outcome
  yapar (`record=None`, uydurma karar yok); program/config hatası yükselir.
  Study başarısızlıkları koşula bağlı `outcomes.jsonl` dosyasına yazar
  (`records + failed == planned`); benchmark aynı yolla devam edip
  `FAILED-EVAL` satırı basar. Katı `run_suite` değişmedi.
- Ayrım: pilot manifestosunda `"bundle_complete": true` (teknik) ve
  `"coverage_sufficient": <full_coverage>` (bilimsel) ayrı alanlardır;
  kısmi koşuda `true`/`false` ayrışır (testle sabit). Study manifestosu
  bayt-kararlılığı için değişmedi.

## Değişen / yeni dosyalar

- `experiments/bundle.py` (`open_result_dir`), `cli/main.py` (4 sınır +
  FAILED-EVAL), `scripts/llm_bench.py` (doğrulanmış tüketim),
  `mutations/materialize.py` (defter + denklemler),
  `scoring/harness.py` (izolasyon), `experiments/study.py` (outcomes),
  `experiments/pilot.py` (iki ayrım alanı).
- Yeni testler (21): `test_materialization_outcomes.py` (8),
  `test_evaluator_isolation.py` (5), `test_reader_boundary.py` (8).
- Açıkça değişen beklenti (1): `test_study_preflight` iç casusu
  `run_suite_with_outcomes` adını yamalar (aynı niyet).
- R3 diff'i: `e3b.diff` (başlangıç snapshot'larına karşı).

## Test / doğrulama

- Hedefli küme: **197 passed**. Tam offline paket: **319 passed**
  (298 baz + 21 yeni). ruff check/format, mypy temiz. Sıfır canlı istek.
- Gerçek veri: üretim study konfigürasyonunda 280 planda 43 no-op ilk kez
  defterde görünür (237 yazılan × 2 evaluator = 474 mutated kayıt uzlaşır).

## Deterministik study

Yeni benzersiz kök `/tmp/sloplab-e3b-gHUSfs` (297 cases, 2 evaluators; 594
kayıt). E1e'ye göre bilinçli iki ek (`completion.json`,
`materialization-ledger.jsonl`); ortak 480 hash IDENTICAL, suite-index ham
IDENTICAL, manifestoda yalnız zaman alanları. Yeni paket `complete`
(483 dosya); `run-outputs.sha256` 484/484 doğrulandı. `/tmp` kalıcı arşiv
değildir.
