# E1b — Çalıştırma boyunca sabit rapor girdisi

Durum: Hazır; henüz uygulanmadı. Yürütücü: Luna.  
Kök: `/home/kaan/sloplab`. Önkoşul: [E1a kabulü](reviews/issue-05/E1a-acceptance.md).

## Amaç

`build_cases` türev belgeyi yüklerken hedefleri alıyor fakat rapor nesnesini saklamıyor. `run_case` her evaluator için aynı türev dosyasını yeniden okuyor. Arada dosya değişirse sabit hedeflerle farklı metin değerlendirilebilir. Pilotun `_document_for` yardımcısı da aynı yeniden okuma yoluna sahip.

Bu pakette **build_cases ile oluşturulmuş vakaların raporunu ve hedeflerini çalışma süresince sabit tut**. Rapor ve türev hedefleri aynı yüklenen fixture'dan alınmalı; sonra dosyanın değişmesi ya da silinmesi evaluator girdisini değiştirmemeli. Bu, yükleme tamamlandıktan sonraki tutarlılık garantisidir; yükleme sırasında tüm dosya sisteminin atomik snapshot'ı alındığını iddia etme.

Tam StudySpec/CaseSnapshot mimarisi, yeni içerik hash'i veya veri şeması sürümü tasarlama. Mevcut dondurulmuş `ReportDocument` kullanılabilir. Performans kazancı iddiası için profil zorunlu değil; burada kabul ölçüsü tekrar okumanın kaldırılması ve davranış eşdeğerliğidir.

## Okuma kapsamı

Önce geçerli AGENTS.md yönergelerini oku. Ardından:

- `src/sloplab/scoring/harness.py`: SuiteCase, build_cases, run_case.
- `src/sloplab/models/report.py`, `src/sloplab/models/evaluation.py`: belge ve context.
- `src/sloplab/corpus/loader.py`: canonical/derived fixture veri yapıları ve yükleyiciler.
- `src/sloplab/experiments/pilot.py`: yalnız `_document_for` ve belge tüketimi; LLM çağrısı yapma.
- `src/sloplab/experiments/study.py`: çağrı sınırı; E1a preflight korunacak.
- `tests/regression/test_remediation_v022.py`, `tests/unit/test_llm_pilot.py`, ilgili harness/CLI/study testleri ve fixture yardımcıları.

`SuiteCase(...)` doğrudan kurucularını `rg` ile envanterle. Tüm repo veya bilimsel raporları bağlama yükleme. Ek dosyayı yalnız doğrudan bağımlılık için oku; alt ajan başlatma.

## Davranış sözleşmesi

1. `build_cases` hem canonical hem mutated vaka için hazır rapor girdisini saklar. Türev manifest ve metni aynı `load_derived_fixture` sonucundan alınır.
2. Bu yolla oluşturulan vakalarda `run_case` diskten yeniden fixture/rapor yüklemez. Pilot belge seçimi de aynı saklanmış raporu kullanır. Mevcut yardımcıya dar değişiklik yapılabilir veya ortak belge erişim fonksiyonu kullanılabilir.
3. `expected_dimensions` kaynaktan kopyalanmış olmalı; evaluator'a verilen mutable etiket kopyasının değiştirilmesi sonraki evaluator'ı veya CaseRecord hedeflerini değiştirmemeli. Frozen dataclass içindeki dict'in kendiliğinden immutable olmadığını gözet. Bu fazda label erişimi/oracle protokolünü yeniden tasarlama.
4. R04 kimlik gizleme davranışı korunur: gerçek case/path/mutation kimliği evaluator'a sızmamalı; opaque handle ve CaseRecord'a gerçek kimliğin geri konması aynı kalmalı. Pilotun başka mevcut kimlik kusurlarını bu fazda kendiliğinden genişletme.
5. Vaka sırası, evaluator sırası, seed'ler, hedefler, kararlar, metrikler ve serialization değişmez.
6. Doğrudan `SuiteCase` kuran mevcut çağrılar bilinçli ele alınır. Tercih: yeni snapshot alanını geriye uyumlu ekle, build_cases yolunda zorunlu doldur. Legacy yükleme fallback'i gerekiyorsa açıkça belgele ve yalnız snapshot'ı olmayan eski kurucularla sınırla; build_cases yolu asla bu fallback'e düşmesin. Legacy fallback'i tam snapshot garantisine dahil etme.

Saklanan belge alanını optional yapmak veya ortak accessor eklemek gibi rutin seçimleri kendin çöz. Tüm veri modellerini yeniden yazma. Source/manifest dosyalarının yükleme sırasında değişmesine karşı atomik okuma, içerik kimliği ve stimulus doğrulaması sonraki paketlerdir.

## Değişiklik sınırları

İzinli: harness, pilotun belge seçme yardımcısı, ilgili testler ve kısa sözleşme açıklaması. Gerekli tip importları eklenebilir. Diğer modüllere ihtiyaç doğarsa önce mevcut yapıda küçük çözümü araştır; kapsamı genişleten tasarımı uygulamadan teslimde açıkla.

E1a'nın dirty uygulama değişiklikleri kullanıcı tarafından kabul edilmiştir; koru. Başlangıçta dosya hash/diff envanteri al. Kendi E1b değişikliğini E1a ile birleştirilmiş git diff'ten ayırarak teslim et; untracked E1a testini unutma. Commit/push/branch değişikliği, canlı API, ağdan kurulum, lock/config/korpus/altın sonuç değişikliği yok.

## Zorunlu testler

- Geçici materyalize suite'te `build_cases` çağır; sonra türev report ve mutation manifest içeriğini değiştir. Birden fazla evaluator aynı ilk metni/ilk hedefleri görmeli. Yalnız sonucu assert etmek yerine gördükleri girdiyi spy ile kaydet.
- Ayrı örnekte yükleme sonrası türev dosyalarını kaldır veya geçici başka konuma taşı: snapshot'lı vaka hâlâ değerlendirilmeli. Yalnız testin kendi geçici dosyalarını kullan.
- `build_cases` bittikten sonra yükleyiciyi çağrılırsa hata verecek şekilde monkeypatch et: snapshot'lı `run_case` ve pilotun belge seçimi bu yükleyiciye dokunmamalı. Pilot için fake evaluator/client kullan; gerçek provider akışına girme.
- Canonical rapor için de yükleme sonrası disk değişiminin etkisizliğini doğrula.
- Bir evaluator context içindeki expected_dimensions kopyasını değiştirince sonraki evaluator'ın hedefleri ve kayıt beklentileri korunmalı.
- Mevcut R04 kimlik testleri, doğrudan SuiteCase kurucu uyumluluğu, E1a erken ret testleri ve fake pilot testleri geçmeli.

Kalıcı regresyon testleri ekle; yalnız implementation çağrı sayısını taklit eden testlerle yetinme. Fonksiyonların yanlış girdiyi kullanması halinde test gerçekten başarısız olmalı. Kaynak düzenlemesinde `apply_patch` kullan.

## Doğrulama ve teslim

Önce yeni testler ile ilgili mevcut R04/study/preflight/fake-pilot testlerini çalıştır. Değişen dosyalarda lint/format/type kontrollerini ve geçerli repo yönergelerinin zorunlu kontrollerini uygula. Aynı kontrolleri yeni gerekçe olmadan tekrarlama.

Yeni ve çakışmayan `/tmp/sloplab-e1b-XXXXXX` dizininde bir offline deterministik study üret. E0 `run-a` veya kabul edilmiş E1a `/tmp/sloplab-e1a-ppqPYl/run` ile tam dosya kümesi ve ham hash karşılaştırması yap. 479 veri/index dosyasının ham eşitliği beklenir; manifestoda aynı kök/commit koşulunda yalnız zaman farkı kabul edilir. Sayıları ayrıca ölç; golden uydurma veya güncelleme yapma. Referans yoksa eksikliği bildir.

Teslim: `docs/reviews/issue-05/E1b/` (doluysa yeni numaralı kardeş).

- `README.md`: davranış, uygulama tercihi, garanti sınırı, değişen/yeni dosyalar ve E1b durumu.
- `commands.jsonl`: gerçek komut, cwd, **asıl komutun** exit code'u, kalıcı stdout/stderr bağlantıları. Shell'in son `echo` başarısını testin exit code'u olarak kaydetme.
- `comparisons.md`: tam dosya kümesi, ham eşitlik, manifesto alan farkı, vaka/kayıt sayıları.
- Başlangıç/bitiş ilgili kaynak hash'leri, yeni run hash envanteri ve test günlüklerini teslim içinde sakla. Tam büyük run dizini `/tmp` içinde kalabilir; yolu ve saklama sınırını belirt.

Başlangıçta var olan E1a diff'inden ayrı E1b diff'ini üret; yeni test dosyaları da teslim listesinde bulunsun. İş bittiğinde dur. **E1b kabulü, E1'in tamamının veya legacy kurucuların tümünün değişmezleştirildiği anlamına gelmez.** Sonraki paket Astra incelemesinden sonra verilecek.
