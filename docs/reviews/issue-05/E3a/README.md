# E3a — Bundle envanteri, tamamlanma işareti ve doğrulayan okuyucu

Önkoşul: [E2b-r2 kabulü ve E2 kapanışı](../E2b-r2-acceptance.md). Ortak
kurallar: [worker teslim protokolü](../../issue-05-worker-delivery-protocol.md).
Önceki kanıtlar değiştirilmedi. E3 kapanmadı; canlı pilot ilan edilmedi.

## Uygulanan davranış

- Yeni modül `src/sloplab/experiments/bundle.py`: deterministik
  `completion.json` (şema + tür + sıralı dosya→sha256 haritası; zaman
  damgasız), `write_completion` (yalnız tüm dosyalar sonrası çağrılır;
  tür asgarisini ister), `verify_bundle` (işaret + tür + asgari küme +
  bire bir dosya kümesi + her dosyada hash; ilk ihlalde `BundleError`),
  `classify_bundle` (`complete` / `incomplete` / `legacy`; işaretsiz
  kesintiye uğramış yayın da legacy biçimli görünür ve reddedilir;
  dönüştürme yok).
- Yayın sınırları: `run_llm_pilot` (records/outcomes/manifest sonrası işaret;
  `completion_path` eklendi) ve CLI `study` (analysis/CSV/rapor sonrası
  işaret). `run_deterministic_study` işaret yazmaz (kütüphane adımı);
  `evaluate`/`benchmark` paketleri legacy olarak tanınır (değişmedi).
- Staging iddiası yok: yazarlar dizine yazar, işaret sondur; dosya başına
  rename ötesi atomiklik sunulmaz (sözleşmede açık).
- Korunanlar: E2 kapanış davranışları, mevcut okuyucular (compare/report/
  `read_run_jsonl`/yardımcılar), eski artefaktlar. Metrik hesabı E4,
  legacy tüketimi ve materialization defteri E3b.

## Değişen / yeni dosyalar

- Yeni: `src/sloplab/experiments/bundle.py`,
  `tests/regression/test_bundle_completion.py` (17 fault-injection testi).
- Değişen: `src/sloplab/experiments/pilot.py` (işaret + `completion_path`),
  `src/sloplab/cli/main.py` (study sonunda işaret).
- Dokunulmayan (snapshot ile sabit): `study.py`, `runner.py`,
  `reporting/writers.py`, `models/run.py` (diff'te hunk yok).
- R3 diff'i: `e3a.diff` (başlangıç snapshot'larına karşı).

## Test / doğrulama

- Yeni 17 test: pilot sınırında eksik/bozuk/takas/fazla/silinen işaret/
  kurcalanmış işaret/tür uyuşmazlığı/eksik küme; işaret-sırası casusu;
  study sınırında eksik analiz/bozuk identity/karışık run; doğrudan koşucu
  çıktısının legacy görünmesi; committed örneğin legacy tanınması; boş dizin.
- Hedefli küme: **166 passed**. Tam offline paket: **296 passed**
  (baz 279 + 17 yeni). Not: E2b-r2 kabulü 280 yazmıştı; bu çalışmada
  atlanan test yokken toplanan baz 279'dur (tümü yeşil); tek sayılık fark
  inceleyici sayım artifaktı olarak kaydedildi, yük taşıyan olgu
  toplananların tamamının geçmesidir.
- ruff check/format, mypy temiz. Sıfır canlı istek.

## Deterministik study

Yeni benzersiz kök `/tmp/sloplab-e3a-EPC7GP` (297 cases, 2 evaluators; 594
kayıt: canonical 120 + mutated 474). E1e'ye göre bilinçli tek fark
`completion.json` eklenmesidir (ortak küme 480/480 hash IDENTICAL,
suite-index ham IDENTICAL, manifestoda yalnız zaman alanları). Yeni paket
strict reader ile doğrulanır (`complete`); E1e referansı `legacy` tanınır.
`/tmp` kalıcı arşiv değildir; kalıcı kanıt bu teslimdeki kopyalardır
(`run-outputs.sha256`: 483/483 doğrulandı).
