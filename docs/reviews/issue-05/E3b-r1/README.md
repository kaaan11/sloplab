# E3b-r1 — Legacy ile kesilmiş yeni yayını ayıran yayın protokolü

Önkoşul: [E3b revizyon kararı](../E3b-acceptance.md). Ortak kurallar:
[worker teslim protokolü](../../issue-05-worker-delivery-protocol.md).
Önceki kanıtlar değiştirilmedi (aşağıdaki teslim-bütünlük notu hariç
hiçbir eski dosyaya dokunulmadı). E3 kapanmadı; canlı pilot ilan edilmedi.

## Uygulanan davranış

- Yayın protokolü (`experiments/bundle.py`): `begin_publish` (in-progress
  işareti + eski completion'ın emekliliği; idempotent) ve `finish_publish`
  (doğrulanabilir completion + işaretin EN SON kaldırılması). Yazarlar:
  pilot (doğrulama sonrası, ilk dispatch öncesi → sonda kapatma), study
  koşucusu (preflight sonrası, ilk mutasyon öncesi), CLI study (sonda
  kapatma). `verify_bundle`/`open_result_dir`/`classify_bundle` önce
  in-progress bakar: işaret varken completion geçerli olsa bile ret;
  completion haritası protokol işaretlerini kapsamaz.
- Yayıncı-iç okuma kuralı: aynı sürecin kendi ara çıktısını okuması
  (CLI study'nin analiz öncesi kayıt okuması) tüketim değildir; kapı onu
  kilitlerdi. Yayın-dışı her okuma (compare, report, llm_bench, sonraki
  süreçler) kapıdan geçer. Yayın sırasında aynı baytlara yönelen kapı
  okuması reddedilir (testle sabit).
- Korunanlar: E3b defteri/izolasyon/ayrım davranışları, mevcut okuyucular,
  eski artefaktlar. Şema değişmedi (yeni dosya yok).
- Açıkça değişen beklentiler (3 test): E3b
  `test_study_runner_output_without_publish_is_legacy` → `..._is_incomplete`
  (doğrudan koşucu çıktısı artık belirsiz değil); E3a rewrite casusu yeni
  gözlem noktasına (koşucu-`begin` sonrası ilk mutasyon); patlayan
  evaluator testinde kesinti artığı (`incomplete`, kayıtsız) beklentisi.

## Değişen / yeni dosyalar

- `experiments/bundle.py` (işaretler + okuyucu sırası),
  `experiments/pilot.py` (aç/kapa), `experiments/study.py` (aç),
  `cli/main.py` (kapa + iç-okuma kuralı).
- Dokunulmayan (diff'te hunk yok): `materialize.py`, `harness.py`,
  `llm_bench.py` (davranışları aynen korunur).
- Yeni testler (12): `tests/regression/test_publish_protocol.py`
  (başlangıç görünürlüğü, kesinti redleri, yeniden-yazım yarışları,
  okuyucu bypass'ları, tarihsel ağaç dokunulmazlığı, yayın-ortası ret).
- R1 diff'i: `e3b-r1.diff` (başlangıç snapshot'larına karşı; 4 dosyada
  hunk, 125 değişen satır).

## Test / doğrulama

- Hedefli küme: **209 passed** (197 + 12 yeni). Tam offline paket:
  **331 passed** (319 + 12). ruff check/format, mypy temiz. Sıfır canlı
  istek (fake transport + sahte saatler + yamalı `urlopen`).
- Tarihsel kirlenme bulgusu ve düzeltmesi: E3b
  `test_report_reads_legacy_openly` testi committed
  `benchmarks/results/v1-core-example/report.md` dosyasını sessizce
  yeniden yazmıştı (tek satır başlık farkı). Teslim öncesi `git checkout`
  ile geri alındı; test `--out tmp` kullanacak biçimde düzeltildi;
  `test_historical_tree_untouched_by_readers` regresyon bekçisi eklendi.
  Teslim anında `git diff --stat -- benchmarks/` boştur.

## Teslim-bütünlük notu (olay kaydı)

Teslim montajı sırasında `docs/reviews/issue-05/E3b-r1/` altındaki
başlangıç kanıtları (`start/`, `hashes-start.txt`, `logs/` kopyaları
henüz taşınmamıştı) paylaşımlı makinedeki harici bir etkenle silindi;
daha sonra yazılan `publish-state-contract.md` kurtuldu. Kayıp, aşağıdaki
yöntemle eksiksiz telafi edildi:

- `start/materialize.py`, `start/harness.py`, `start/llm_bench.py`: R1
  bunlara dokunmadı; güncel kopyalar E3b `hashes-end.txt` hash'leriyle
  birebir doğrulandı.
- `start/bundle.py`, `start/pilot.py`, `start/study.py`, `start/main.py`:
  oturum değişim günlüğünün birebir tersi uygulandı; dördü de E3b
  `hashes-end.txt` hash'leriyle birebir doğrulandı (`bundle`
  `d2806f38`, `pilot` `912ef77f`, `study` `c0d60776`, `main` `4c511ec5`;
  bundle'daki E3b docstring revizyonu E3b `e3b.diff` içeriğiyle çapraz
  doğrulandı).
- `hashes-start.txt` bu doğrulanmış dosyalardan yeniden üretildi
  (`sha256sum -c` ile kendini doğrular).
- Çıkarılan ders: kanıt dizini montajı tek seferde ve hızlı kapatılmalı;
  ara ürünler doğrulanmadan oturum sonu beklenmemeli.

## Deterministik study

Yeni benzersiz kök `/tmp/sloplab-e3b-r1-Rs1HvD` (297 cases, 2
evaluators; 594 kayıt). E1e'ye göre bilinçli iki ek (`completion.json`,
`materialization-ledger.jsonl`); ortak 480 hash IDENTICAL. Yeni paket
`complete` (483 dosya, in-progress artığı yok); `run-outputs.sha256`
484/484 doğrulandı. `/tmp` kalıcı arşiv değildir.
