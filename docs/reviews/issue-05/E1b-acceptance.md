# E1b — Ana inceleyici kabul kararı

Tarih: 2026-09-09. İnceleyici: Astra. **E1b kabul edildi; E1 bütünü açık.**

Harness/pilot diff'i, 11 yeni snapshot testi ve teslim kanıtları incelendi.
`build_cases` canonical ve mutated raporları saklıyor; `case_document` bunları
öncelikli kullanıyor. `run_case` ve pilot belge seçimi aynı accessor'a bağlı.
Hedefler evaluator context'ine ve CaseRecord'a ayrı sözlük kopyalarıyla aktarılıyor.
Legacy kurucular için fallback korunmuş; snapshot garantisi bu yola genişletilmiyor.

Ana inceleyici tarafından çalıştırılan komutlar:

```bash
uv run --offline --frozen pytest -p no:cacheprovider tests/regression/test_case_snapshot.py tests/regression/test_remediation_v022.py tests/regression/test_study_preflight.py tests/unit/test_experiments.py tests/unit/test_llm_pilot.py
python3 -B docs/reviews/issue-05/E0/helpers/compare_e0.py /tmp/sloplab-e0-zVHDyy/run-a /tmp/sloplab-e1b-ihv1hN/run /tmp/sloplab-e0-zVHDyy/run-a
git diff --check
```

54 test geçti; karşılaştırma `RESULT: OK`; diff kontrolü temiz. 480 dosyalık
küme aynı; 479 dosya ham eşit, manifesto yalnız zamanlarda farklı. Yeni study
ve tam test paketi bu incelemede tekrar çalıştırılmadı. Worker'ın 225 test
beyanı, ana inceleyicinin yeniden çalıştırdığı 54 testten ayrıdır.

Teslim kayıt kusuru: `hashes-start.txt` içindeki study.py hash'i 75 karakter.
Başlangıç/bitiş eşitliği iddiası bu dosya için geri çekildi; README düzeltildi,
orijinal envanter korunarak geçmiş kanıt uydurulmadı. Bitiş envanterindeki tüm
dosya hash'leri güncel dosyalarla doğrulandı. Diğer korunan E1a dosyaları için
başlangıç/bitiş hash'leri eşit; study.py uygulama diff'i önceki kabul edilen
E1a değişikliğiyle uyumlu ve preflight testleri geçiyor.

Uygulamada bloklayıcı hata bulunmadı. `run_case` docstring'indeki yeniden okuma
olmaması yalnız snapshot'lı vakalar için geçerlidir; accessor'ın belgelediği
legacy istisna sürer. Arbitrary in-process SuiteCase dict değişikliğine veya
yükleme sırasında eşzamanlı dosya değişimine karşı tam immutability iddiası yok.

Sonraki paket: [E1c — Gönderilen prompt ile kaydedilen kimliği bağlama](../../issue-05-E1c-task.md).
