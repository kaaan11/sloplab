# E0 — Luna için referans ve bulgu doğrulama görevi

Durum: Hazır; henüz yürütülmedi.  
Tarih: 2026-09-09  
Çalışma kökü: `/home/kaan/sloplab`  
Üst plan: [Mühendislik değerlendirmesi ve planı](issue-05-engineering-assessment-and-plan.md)  
Kaynak rapor: `/home/kaan/GPT-Pro/reports/issue-05-Sloplab.report.md`

## 1. Görevin ve duracağın sınır

Sen bu fazın doğrulama yürütücüsüsün. Amaç, rapordaki mühendislik bulgularının güncel çalışma ağacındaki durumunu belirlemek ve sonraki değişikliklerin karşılaştırılacağı referansı kurmaktır. Kod düzeltmesi yapma. E1'e kendiliğinden geçme. Teslimi ana inceleyici Astra değerlendirecek.

Üç soruyu kanıtla yanıtla:

1. Tam olarak hangi kod, config, korpus ve ortam incelendi?
2. Aynı girdilerle iki yeni offline çalışma aynı deterministik çıktıları veriyor mu; eski kayıtlarla ilişkileri ne?
3. Kaynak raporun kritik bulgularından hangileri güncel kodda sürüyor, hangileri giderilmiş veya henüz doğrulanamıyor?

Bir kusur veya eşitsizlik bulmak başarısız görev demek değildir. **Doğrulama tesliminin tamamlanması** ile **yeniden üretim kapısının geçmesi** ayrı sonuçlardır. Gerçeği kaydet; çıktıyı beklenen sayıya uydurma.

## 2. İzin verilen işlemler

- Yerel yönergeleri, aşağıda kapsamı verilen dosyaları ve gerekli doğrudan bağımlılıklarını oku.
- Read-only git/ortam kontrolleri, yerel hash envanteri, iki offline study ve ilgili mevcut offline testleri çalıştır.
- Yeni teslim dizinine raporlar, komut günlükleri, envanterler ve küçük doğrulama yardımcıları yazabilirsin. Yardımcı kodu da teslim et; proje uygulamasına veya test paketine ekleme.
- Her çalışmanın verisini yeni ve boş çıktı dizininde üret. Geçici çıktıları kullanıcıya teslimden önce silme.

Şunları yapma:

- `src/`, `tests/`, korpus, mevcut config, lock dosyası, `.gitignore`, eski sonuçlar veya mevcut kullanıcı belgelerini değiştirme.
- Bug fix, refactor, yeni regresyon testi, etiket/metrik/evaluator/seed değişikliği yapma.
- Canlı LLM, harici servis, ağdan kurulum, fetch/pull, commit/push veya branch değiştirme işlemi yapma.
- Bilimsel rapor dizinini (`/home/kaan/GPT-Pro/reports/sloplab-bilimsel`) ya da diğer projeleri tarama.
- Yeni alt ajan başlatma. Bu faz tek yürütücüyle sınırlıdır.

Yerel bağımlılık eksikse kanıtını kaydet; kurulumu bu görevin içine genişletme. Yalnız bağımlılığa ihtiyaç duyan kontrolü engellenmiş say; bağımsız statik incelemeye devam et. Platform izin istemek zorundaysa buna uy; dosya izinlerini veya sandbox'ı aşmaya çalışma.

## 3. Okuma sırası ve bağlam sınırı

Önce geçerli `AGENTS.md` yönergelerini ve bu görev dosyasını oku. Üst plandan E0 ile çalışma sınırlarını oku. Kaynak raporu bölüm bölüm okuyarak B1–B12/U1–U12 bulgu dizinini çıkar; tamamını tekrar tekrar bağlama yükleme.

Repo genelinde toplu dosya dökümü yapma. `rg` ile sembol bul, ilgili fonksiyonu ve çağrı sınırını oku. Aşağıdaki yollar başlangıç noktalarıdır; bir iddiayı çözmek için ek dosya gerekiyorsa doğrudan bağımlılığı takip et ve okuma kaydına nedenini yaz.

| İnceleme | Başlangıç dosyaları |
| --- | --- |
| Ortam ve sözleşme | `pyproject.toml`, `uv.lock` hash'i, `.github/workflows/ci.yml`, `docs/reproducibility.md` |
| Study ve config | `src/sloplab/experiments/{study,runner,config}.py`, `experiments/configs/deterministic-study-v0.2.yaml`, `benchmarks/suites/v1-core.yaml`, `src/sloplab/cli/main.py` içindeki study yolu |
| Kaynak düzenleme | `src/sloplab/mutations/{textops,base,planner,materialize}.py`, `operators/evidence.py` (mutations altında), `src/sloplab/corpus/parser.py` |
| LLM | `src/sloplab/evaluators/llm/adapter.py`, `src/sloplab/experiments/pilot.py`, `scripts/llm_bench.py`, `experiments/prompts/triage-v1.md` |
| Ölçüm ve kayıt | `src/sloplab/scoring/{metrics,comparison,harness}.py`, `src/sloplab/models/{run,evaluation,enums}.py`, `src/sloplab/reporting/writers.py` |
| Tarihsel kanıt | `experiments/results/deterministic/study-v02/` içindeki manifest, index, records, analysis ve rapor; B1 için yalnız ilgili üç türev ve parent |

Hash envanteri için dosyaları programatik okumak, içeriklerini sohbet bağlamına dökmeyi gerektirmez. Büyük `records.jsonl`, `analysis.json` ve `uv.lock` dosyalarını terminale bütünüyle basma.

## 4. Çıktı yerleşimi ve başlangıç kaydı

Teslim dizini olarak `docs/reviews/issue-05/E0/` kullan. Bu dizin zaten doluysa üzerine yazma; yeni `E0-02`, `E0-03` gibi ilk kullanılmayan kardeş dizini seç ve raporda belirt. Geçerli alt dizin yönergelerini yazmadan önce kontrol et.

Çalıştırma verisi için `mktemp -d /tmp/sloplab-e0-XXXXXX` ile bir dizin oluştur. Gerçek yolu rapora yaz. Altındaki `run-a/`, `run-b/` ve `logs/` ayrı olsun. Shell değişkeni gerekiyorsa `E0_RUN_ROOT` gibi göreve özgü ad kullan; `HOME` veya `CODEX_HOME` kullanma.

İlk kayıtta şunlar bulunmalı:

- `git rev-parse HEAD`, branch/detached durumu, `git status --porcelain=v1`, tracked/staged diff özeti.
- Sonucu etkileyen dirty dosyaların diff'i; untracked kaynak/config/girdi dosyalarının kimliği. Credential veya ilgisiz özel içerikleri rapora kopyalama.
- Python executable ve sürümü, platform, `uv --version`, kullanılan paket sürümleri; `uv.lock` ve `pyproject.toml` hash'leri.
- Kaynak rapor, kullanılan source/config dosyaları ve canonical rapor/manifest dosyaları için köke göre göreli yol + SHA-256 envanteri.
- Eski `study-v02` ağacındaki tüm dosyaların göreli yol + SHA-256 envanteri; eksik dosyaları ayrıca belirt.

Bu görev hazırlanırken HEAD `9960f4fd517ff9ede511aebea0b7e2db9305819e` idi. Bunu güncel kabul etme; tekrar ölç. Kullanıcının mevcut `.gitignore`, `.claude/`, `arastirma.md`, `muhendislik.md` ve plan belgelerindeki çalışmalarını koru.

Eski manifestin kaydettiği commit'i dosyadan çıkar. Yerelde commit nesnesi var mı, HEAD ile ilişkisi ne, ilgili tag mevcut mu read-only kontrol et. Tag bulunamaması, remote'da bulunmadığını kanıtlamaz. Eski commit'e checkout yapma ve onu çalıştırma: tarihsel ortamda yeniden üretim bu fazda zorunlu değildir. HEAD ile eşitlik çıkması da eski commit'in kendi ortamında yeniden üretildiği anlamına gelmez.

## 5. Karşılaştırma politikasını çalıştırmadan önce yaz

`comparison-policy.md` dosyasını mevcut serializer ve CLI akışını okuyarak oluştur. Çıktıları gördükten sonra testi geçirmek için kapsamı daraltma. Politika değişirse gerekçeyi ve önceki sonucu koru.

| Çıktı | Zorunlu karşılaştırma |
| --- | --- |
| `records.jsonl` | Ham bayt ve satır sırası eşitliği. Sıralayarak veya ilk satırı atarak eşit gösterme. |
| `adversarial/` | Önce iki yönlü göreli dosya kümesi eşitliği; ardından tüm dosyaların ham hash karşılaştırması. |
| `suite-index.jsonl` | Ham hash ve yapılandırılmış alan farkları; yolları otomatik silme. |
| `analysis.json` ve CLI'nin ürettiği diğer analiz dosyaları | Dosya varlığı, ham hash ve gerekirse alan bazında değer farkları. Beklenmedik float farklarını yuvarlayarak kapatma. |
| `report.md`, varsa CSV/diğer çıktılar | Ham karşılaştırma; farkı veri veya sunum düzeyinde sınıflandır. |
| `manifest.json` | Ham farkı sakla; zaman gibi önceden belirlenmiş değişken alanlar için ayrıca alan bazlı karşılaştırma yap. Kimlik/seed/config farklarını örtme. |

Yeni/yeni karşılaştırma ile eski/yeni karşılaştırma farklıdır: eski commit, mutlak yollar veya şema farkları raporda açıkça gösterilir. Normalize eşitlik, ham bayt eşitliği olarak adlandırılmaz. Çıktıda beklenmeyen yeni/eksik dosya varsa kapsam dışına atma.

## 6. İki offline çalışma ve mevcut testler

Önce config'in yalnız deterministik evaluator'ları seçtiğini ve CLI'nin `--out` yoluna yazdığını doğrula. Aşağıdaki komutları repo kökünden çalıştır; `GERCEK_E0_DIZINI` yer tutucusunu oluşturduğun gerçek geçici dizinle değiştir:

```bash
uv run --offline --frozen sloplab study experiments/configs/deterministic-study-v0.2.yaml --out /tmp/GERCEK_E0_DIZINI/run-a
uv run --offline --frozen sloplab study experiments/configs/deterministic-study-v0.2.yaml --out /tmp/GERCEK_E0_DIZINI/run-b
```

Ortam/cache için yazılabilir bir konum gerekirse göreve özel geçici cache/venv kullanılabilir; dependency/lock sürümleri değiştirilemez ve ağdan indirme yapılamaz. Offline ortam hazırlığı başarısızsa sınırsız tekrar yapma; stderr ve exit code ile engeli kaydet.

İki çalışma aynı sabit girdiyi kullanmalı. Girdi hash'lerini başlangıçta ve bitişte karşılaştır. Arada kaynak/config/korpus değişmişse bu çift determinism kanıtı değildir; karışmış girdi olarak raporla.

Her komut için cwd, tam komut, başlangıç/bitiş, exit code ve stdout/stderr dosya yolunu kaydet. `cmp`/`diff` için fark bildiren exit code'u komutun çalışamamasıyla karıştırma. Başarısız study'nin kısmi çıktısını başarılı çalışma diye analiz etme.

İlgili mevcut testleri bir kez çalıştır:

```bash
uv run --offline --frozen pytest -p no:cacheprovider tests/unit/test_experiments.py tests/regression/test_calibration_binning.py tests/regression/test_suite_paths.py
```

Önce seçilen testlerin güncel içeriklerini ve `conftest.py` yan etkilerini kontrol et. Testlerin geçmesi rapordaki karşıörneklerin kapsandığı anlamına gelmez. Gerekirse LLM/mutation bulgusuna yönelik mevcut fake testlerden dar bir seçim ekle; seçimin gerekçesini yaz. Tüm test paketini, lint/typecheck'i veya performans profilini otomatik başlatma.

## 7. Kritik bulgu matrisi

Her satırda bulgu ID'si, iddia, güncel `dosya:satır`, kanıt türü, durum, erişilebilirlik, mevcut artefakt etkisi ve sonraki faz bulunmalı. Kod mekanizmasını doğrulamak, üretimde gerçekleştiğini doğrulamak değildir.

Durum sözlüğü: `DOĞRULANDI`, `GİDERİLMİŞ`, `ÇÜRÜTÜLDÜ`, `BU_GİRİŞTE_ERİŞİLEMEZ`, `BELİRSİZ`. Kanıt türünü ayrıca `kod / kayıtlı artefakt / bu tur çalıştırıldı` olarak yaz. “Bir girişte erişilemez” bulguyu bütün sistem için çürütmez.

Öncelikle şu satırları tamamla:

| ID | Kontrol |
| --- | --- |
| B1 | `totiming-019`, `oauthstate-029`, `saml-019` için parent/türevde silinen adım ve kalan devam satırı; güncel silici mekanizması. Üç örnek toplam etki sayısı değildir. |
| B8/U1 | Hash'lenen prompt ile gerçekten render edilip gönderilen prompt aynı mı? Çağrı yolunu göster; canlı istek yapma. |
| B8 | `_failed_result` veya karşılığı karar üretiyor mu; metrik tüketicisi bunu dışlıyor mu? |
| B8 | Fiziksel cap ve retry sahipliği; script yolu ile doğrudan pilot çağrısını ayrı değerlendir. |
| B8/U2/U9 | Severity dönüşümü; türevlerin kind/dimensions aktarımı ve full config'in gerçek vaka seçimi. |
| B10/U4 | Susceptibility'de parent/child ağırlıkları; rapordaki sıfır davranış değişimi karşıörneğiyle formülü değerlendir. |
| B10/U3 | ECE son bininde `1.0` ile `[0.9,1.0)` birlikteyken davranış; mevcut test bunu gerçekten kapsıyor mu? |
| B10 | Eksik repeat'in unanimous sayılabilmesi ve beklenen repeat sayısının kontrolü. |
| B11 | `correct` alanının farklı tüketicileri ve `compare` için kullanılan gerçek giriş dosyaları. |
| B11/U11 | Writer/reader tamamlanma sınırı ve safety-blocked planların görünürlüğü. Kesinti olmuş gibi iddia etme. |
| B12 | Study seed/generation seed ayrımı ve uygulanmadan hash'lenen evaluator ayarları. |
| B3/B12/B8 | Raporda reddedilen `:02d`, smoke fallback ve CLI `max_cases=None` iddiaları. |

Kalan B/U maddelerine kısa durum veya açık erteleme gerekçesi ver; hiçbirini sessizce kapandı sayma. B1'in tam etki envanteri, tüm config kombinasyonları, crash injection, çapraz Python/kök testleri ve eski kayıtların bağımsız metrik yeniden hesabı bu fazda zorunlu değildir; ilgili sonraki faza bağla. E0'ı tam denetim projesine büyütme.

## 8. Teslim dosyaları

Seçtiğin teslim dizininde şu dosyaları oluştur:

- `README.md`: en fazla yaklaşık 1000 kelimelik karar özeti, görev/kapı durumları, HEAD/ortam, kritik bulgular, engeller ve önerilen sonraki dar iş. Diğer dosyalara bağ ver.
- `findings.md`: kritik matris ve diğer B/U maddelerinin durumu.
- `comparison-policy.md`: önceden belirlenmiş eşitlik ve değişken alan politikası.
- `comparisons.md`: A/B ve tarihsel/A sonuçları; dosya, vaka, evaluator ve alan düzeyinde fark sayıları; açıklanamayan farklar.
- `environment.md`: kod/girdi/ortam kimliği, dirty çalışma kapsamı, tarihsel commit/tag ilişkisi ve incelenen ek dosyalar.
- `commands.tsv`: komut, cwd, exit code ve log bağlantıları; çalıştırılmayan işlemleri çalıştırılmış gibi listeleme.
- `inventories/`: başlangıç/bitiş girdileri, eski artefakt ve A/B çıktı hash listeleri. Büyük tabloları README'ye yapıştırma.
- `helpers/`: varsa karşılaştırma yardımcılarının kaynakları ve nasıl çalıştırıldıkları.

Tam run çıktıları geçici dizinde kalabilir; mutlak yollarını ve hash envanterlerini kalıcı teslimde tut. İnceleme tamamlanana kadar korunmaları gerektiğini belirt. `/tmp` kalıcı arşiv değildir; yalnız burada duran veri için uzun vadeli saklama garantisi verme.

Özette vaka sayısını evaluator kayıt satırı sayısından ayır. Kaynak rapordaki 297'yi doğrulanmış beklenen değer diye hard-code etme; canonical, derived, evaluator başına kayıt ve toplam satırı ölçerek yaz. Kayıp/eklenen dosyalar ile karar/hedef/metric/metadata farkları ayrı sayılmalı.

## 9. Kapanış ölçütleri

İki ayrı sonuç ver:

**Görev durumu:** `TAMAMLANDI` veya `KISMİ_ENGELLİ`. Kritik matris, envanter ve yapılabilen kontroller teslim edilmiş olmalı. Çalıştırma engeli varsa hangi kanıtın eksik kaldığı açık olmalı.

**G0 kapısı:** `GEÇTİ`, `KALDI` veya `DEĞERLENDİRİLEMEDİ`.

- `GEÇTİ`: A/B başarıyla tamamlanmış; sabit girdiler doğrulanmış; önceden tanımlanan deterministik çıktılarda açıklanmayan fark yok; tarihsel/A farkları belgeli ve açıklanmış.
- `KALDI`: değerlendirme yapılabilmiş fakat açıklanamayan deterministik fark, girdi kayması veya tarihsel karşılaştırmada çözülememiş fark var. Bunları düzeltmeden teslim et.
- `DEĞERLENDİRİLEMEDİ`: gerekli ortam/artefakt olmadığı veya çalışma tamamlanamadığı için eşitlik hakkında sonuç çıkarılamıyor.

G0'ın geçmesi bütün bug'ların giderildiği veya tarihsel çalışmanın kendi commit'inde yeniden üretildiği anlamına gelmez. Kritik bug'lar devam ederken de tutarlı bir karakterizasyon tabanı kurulabilir.

Son olarak başlangıç/bitiş git durumunu ve korunan girdi/artefakt hash'lerini karşılaştır. İzinli teslim dosyaları ve belgelenmiş geçici çalışma verileri dışında değişiklik bırakma. Beklenmeyen değişiklik gördüğünde kullanıcı değişikliği olabileceğini gözet; otomatik geri alma yapma, raporla.

Teslimden sonra dur. E1 veya düzeltme için sonraki görev paketini bekle.
