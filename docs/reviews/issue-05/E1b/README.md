# E1b — Çalıştırma boyunca sabit rapor girdisi (teslim)

Durum: **E1b tamamlandı** (kabul ölçütleri karşılandı; E1'in tamamı kapanmadı).
Tarih: 2026-09-09. Kök: `/home/kaan/sloplab`. Yürütücü: Luna.
Önkoşul: E1a kabul edildi (`../E1a-acceptance.md`); E1a değişiklikleri korundu
(`cli/main.py`, `test_study_preflight.py` başlangıç/bitiş hash'leri aynı;
`study.py` başlangıç kaydı bozuk olduğundan bu dosya için hash eşitliği kanıtı geçersizdir).

## Davranış

`build_cases` artık her vakanın yüklenmiş raporunu `SuiteCase.report` alanında saklar
(türev manifest + metin aynı `load_derived_fixture` sonucundan). `run_case` ve pilotun
`_document_for` yardımcısı bu snapshot'ı kullanır; çalışma sırasında diskten yeniden
fixture/rapor yüklenmez. Yükleme sonrası dosya değişimi, silme/taşıma evaluator
girdisini değiştirmez.

## Uygulama tercihi

- Yeni alan geriye uyumlu eklendi: `SuiteCase.report: ReportDocument | None = None`;
  `build_cases` yolunda zorunlu doldurulur. Ortak accessor `case_document()` pilot ve
  harness tarafından paylaşılır (pilot tam delege eder; çift fallback mantığı yok).
- Legacy fallback (snapshot'sız doğrudan kurucular: önce `canonical_fixture`, sonra
  disk reload) açıkça belgelendi ve yalnız eski kurucularla sınırlı; `build_cases`
  yolu asla düşmez; fallback tam snapshot garantisine dahil değildir.
- `expected_dimensions`: kaynaktan kopya alınır (değişmedi); evaluator etiket kopyası
  çağrı başına yenilenir (değişmedi); ek olarak `CaseRecord`'a artık açık kopya verilir,
  böylece kayıt–vaka sözlüğü paylaşılmaz. Frozen dataclass içindeki dict'in kendiliğinden
  immutable olmadığı gözetildi. Label/oracle protokolü yeniden tasarlanmadı.
- R04 korundu: opaque handle üretimi ve gerçek kimliğin kayda geri konması aynı;
  evaluator'a gerçek case/path/mutation kimliği sızmaz. Pilotun başka kimlik kusurları
  genişletilmedi.
- Sıra, seed, hedef, karar, metrik, serialization değişmedi (karşılaştırma kanıtlı).

## Garanti sınırı

Bu, yükleme tamamlandıktan sonraki tutarlılık garantisidir; yükleme sırasında dosya
sisteminin atomik snapshot'ı alındığı iddia edilmez. Atomik okuma, içerik kimliği ve
stimulus doğrulaması sonraki paketlerdir. E1b kabulü, E1'in tamamının veya legacy
kurucuların tümünün değişmezleştirildiği anlamına gelmez.

## Değişen / yeni dosyalar

- `src/sloplab/scoring/harness.py`: `report` alanı, `case_document()`, snapshot'lı
  `run_case`, `CaseRecord`'a kopya hedefler.
- `src/sloplab/experiments/pilot.py`: `_document_for` → `case_document` delegesi.
- `tests/regression/test_case_snapshot.py` (yeni, 11 test): disk-değişim görünmezliği
  (spy girdileri), silme sonrası değerlendirme, loader-raise dokunulmazlığı (run_case +
  pilot), canonical değişim etkisizliği, etiket izolasyonu + kayıt ayrışması, legacy
  uyumluluk, build-zorunluluğu, fake-transport pilot snapshot'ı, R04, unloadable ret.
- E1b diff'i: `e1b.diff` (yalnız harness+pilot). E1a korunumu aşağıdaki inceleme
  notundaki kanıt sınırıyla değerlendirilmiştir.
- `apply_patch` aracı bu ortamda yoktur; eşdeğer düzenleme Edit aracıyla yapıldı.

## Test / doğrulama

- Yeni 11 + ilgili mevcut (R04, preflight, experiments, llm_pilot, llm_bench_script, cli,
  pipeline): 70 passed. Tam paket: 225 passed. ruff check/format, mypy: temiz.
- Negatif kontrol: aynı bozuk dosyada legacy yol `FixtureError`, snapshot yolu değerlendirir.
- E0 `run-a` ile tam küme: 480 dosya kümesi eşit, 479 ham eşit (yalnız manifesto zamanları),
  suite-index ham bayt eşit; 297 vaka / 594 kayıt; karar/hedef/metrik farkı yok.

## E1b durumu

**E1b tamamlandı.** Sonraki paket Astra incelemesinden sonra verilecek.

## Astra inceleme notu — 2026-09-09

`hashes-start.txt` içindeki `study.py` değeri 75 karakterdir; geçerli SHA-256
değildir ve bitiş değeriyle eşit değildir. Orijinal kayıt korunmuştur; geçmiş
başlangıç hash'i yeniden ölçülmüş gibi düzeltilmemiştir. Güncel dosyanın bitiş
hash'i doğrulandı. E1a'da kabul edilen kod ile mevcut tracked diff incelemesinde
E1a davranışını değiştiren ek fark görülmedi; E1a testleri yeniden geçti.

Ana inceleyici 54 hedefli testi ve E0 artefakt karşılaştırmasını yeniden
çalıştırdı; hepsi geçti. Ayrıntı: `../E1b-acceptance.md`.
