# Issue 05 — Mühendislik değerlendirmesi ve eylem planı

Tarih: 2026-09-09  
Durum: E0–E5 ve bütünleşik kapanış kabul edildi; zorunlu mühendislik planı tamamlandı. E6 tetiklenmedi, bilimsel kararlar ve canlı pilot ayrı kapı olarak açık. Son güncelleme: 2026-09-10.  
Kaynak: `/home/kaan/GPT-Pro/reports/issue-05-Sloplab.report.md` (663 satır).  
Kaynak SHA-256: `df68dcf2241d40c475681408c4a7c1e5417465ba5d8f798333d4325dbc2c0d7a`  
İnceleme sırasında HEAD: `9960f4fd517ff9ede511aebea0b7e2db9305819e`.

## 1. Sonuç ve kanıt sınırı

### Güncel durum ve kısa devam kaydı

Bu bölüm güncel durumu gösterir; aşağıdaki ilk değerlendirme paragrafları raporun
ilk okunduğu aşamanın kanıt sınırını korur. Ayrıntılı kanıtlar kabul kayıtlarındadır.

| Paket | Durum | Ana inceleyicinin yeniden doğruladığı sonuç |
| --- | --- | --- |
| [E0](reviews/issue-05/E0-acceptance.md) | Kabul | İki koşu ve tarihsel veri eşdeğerliği; yalnız açıklanan provenance farkları |
| [E1a](reviews/issue-05/E1a-acceptance.md) | Kabul | Erken config/evaluator reddi; 20 hedefli test |
| [E1b](reviews/issue-05/E1b-acceptance.md) | Kabul | Sabit rapor snapshot'ı; 54 hedefli test |
| [E1c](reviews/issue-05/E1c-acceptance.md) | Kabul | Prompt kaynağı/render hash bağı; 55 hedefli test |
| [E1d](reviews/issue-05/E1d-acceptance.md) | Kabul | Metin/hedef/seçim kimlikleri; 39 hedefli test ve 297 vaka bağımsız hash kontrolü |
| [E1e](reviews/issue-05/E1e-acceptance.md) | İnceleyici düzeltmesiyle kabul | Mutable config bağı kesildi; son kodla 249 test ve yeni study eşdeğerliği |
| [E2a](reviews/issue-05/E2a-acceptance.md) | İnceleyici düzeltmesiyle kabul | LLM başarısızlığı/karar ayrımı, outcome ledger ve evaluator etiket yetkisi |
| [E2b](reviews/issue-05/E2b-acceptance.md) | Revizyon gerekli | Dispatch sayacı ve toplam deadline sözleşmesi karşıörneklerde bozuldu |
| [E2b-r1](reviews/issue-05/E2b-r1-acceptance.md) | Revizyon gerekli | Deadline yarışı ve direct-pilot pacing bypass'ı açık kaldı |
| [E2b-r2](reviews/issue-05/E2b-r2-acceptance.md) | İnceleyici düzeltmesiyle kabul | Tek yürütme zinciri, exact dispatch muhasebesi ve HTTP deadline; E2 kapandı |
| [E3a](reviews/issue-05/E3a-acceptance.md) | İnceleyici düzeltmesiyle kabul | Bundle envanteri, yeniden yazmada işaret invalidation ve strict reader |
| [E3b](reviews/issue-05/E3b-acceptance.md) | Revizyon gerekli | Kesilmiş yeni yayın legacy yolundan tüketilebiliyor |
| [E3b-r1](reviews/issue-05/E3b-r1-acceptance.md) | İnceleyici düzeltmesiyle kabul | Yarışsız in-progress yayın durumu; E3 kapandı |
| [E4a](reviews/issue-05/E4a-acceptance.md) | İnceleyici düzeltmesiyle kabul | Paired susceptibility, ECE ve repeat-scoped parent bağları |
| [E4b](reviews/issue-05/E4b-acceptance.md) | Revizyon gerekli | Failed coverage, all-failed evaluator ve metric bundle bağı eksik |
| [E4b-r1](reviews/issue-05/E4b-r1-acceptance.md) | İnceleyici düzeltmesiyle kabul | Outcomes bağlı coverage ve yeniden doğrulanan metrikler; E4 kapandı |
| [E5a](reviews/issue-05/E5a-acceptance.md) | İnceleyici düzeltmesiyle kabul | Karakterizasyon, etki envanteri ve kimliğe bağlı span authorization |
| [E5b](reviews/issue-05/E5b-acceptance.md) | Revizyon gerekli | B1 düzeltmesi doğru; splice kapısında kaynak belge kimliği taşınmıyor |
| [E5b-r1](reviews/issue-05/E5b-r1-acceptance.md) | Kabul | Kaynak kimliğine bağlı splice authorization; E5 kapandı |
| [Bütünleşik kapanış](reviews/issue-05/integration-acceptance.md) | Kabul | İki temiz offline run; politika dışı fark yok, zincir/ledger/coverage uzlaştı |
| E6 | Tetiklenmedi | Çapraz ortam garantisi veya ölçülmüş darboğaz kanıtı yok |

Mevcut referanslar: E0 `/tmp/sloplab-e0-zVHDyy/run-a`; bütünleşik kapanış
referansları `/tmp/sloplab-int-a-tgLe3X/run` ve
`/tmp/sloplab-int-b-laUuV5/run`. E1 iki kimlik dosyası,
E3a `completion.json`, E3b materialization ledger ve E4b sürümlü analiz ekler;
güncel toplam 485 dosyadır. Eski 479
veri/index dosyası ham eşit, manifesto zamanları farklı.
Vaka sayısı 297, iki evaluator için kayıt sayısı 594. `/tmp` arşiv değildir.

HEAD hâlâ `9960f4f…`; kabul edilen uygulamalar dirty worktree'dedir. Git HEAD
tek başına incelenen kodu tanımlamaz; yeni/untracked test ve modüller korunmalı.
`.gitignore`, `.claude/`, `arastirma.md`, `muhendislik.md` kullanıcı çalışmasıdır.
Canlı pilot yapılmadı. Bilimsel raporlar `/home/kaan/GPT-Pro/reports/sloplab-bilimsel`
henüz değerlendirilmedi; scientific estimand/CI kararları açık.

Kalan zorunlu mühendislik paketi: **0**. E6 yalnız yeni profil/darboğaz kanıtıyla
açılır. Bilimsel kararlar ve canlı pilot bu planın tamamlanmış sayılan mühendislik
uygulamasından ayrı onay kapılarıdır.

Yeni oturum başlangıcı: bu durum bölümü ile bütünleşik kapanış kabul kaydı
yeterlidir; bütün eski logları yeniden okumak gerekmez. Yeni çalışma ancak açık
bilimsel kararlar, canlı pilot veya kanıtla tetiklenen E6 için ayrı kapsamla
başlatılmalıdır. Bilimsel karar isteyen maddeler sessizce kod tercihine
dönüştürülmeyecek.

Rapor, mühendislik çalışmasının başlangıç belgesi olarak güçlü ve kullanılabilir. Önceliği performans optimizasyonundan deney bütünlüğüne taşıması doğru: hangi girdinin kullanıldığı, hangi çalıştırmanın geçerli gözlem ürettiği ve hangi formülün neyi ölçtüğü belirginleşmeden hız kazanımı sonuçları güvenilir yapmaz.

En değerli katkısı, eski artefaktları korumak ile kusurlu davranışı sürdürmek arasındaki ayrımdır. Tarihsel kayıtlar korunmalı; düzeltilmiş metrikler ve değişen türev içerikleri ayrı sürümlerde üretilmelidir. Refactor eşdeğerliği, analiz düzeltmesi ve veri üretimi düzeltmesi aynı kabul ölçütüne bağlanmamalıdır.

Bu belge raporun tamamının değerlendirmesidir; güncel kodun kapsamlı denetimi değildir. Kaynak rapordaki `VERIFIED` etiketleri rapor yazarının kanıt sınıflandırmasıdır. Bu turda test, benchmark, canlı API veya bağımsız metrik yeniden hesaplaması yapılmadı. Rapordaki dış kaynaklar yeniden doğrulanmadı; burada onlardan yeni bir standart veya literatür iddiası türetilmiyor.

Yerelde HEAD ve çalışma ağacı durumu kontrol edildi. HEAD'in rapordaki export kimliğiyle eşleşmesi, raporun bağlamını destekler; çalışma ağacı veya eski sonuçların eşdeğerliğini kanıtlamaz. Raporda eski sonuç manifestosunun başka commit kaydettiği belirtiliyor; bu bağ G0'da doğrulanmalıdır.

Başlangıçta `.gitignore` değişikliği ile izlenmeyen `.claude/`, `arastirma.md`, `muhendislik.md` vardı. Bunlar kullanıcı çalışması olarak korunmuştur. Ana değerlendirmeye ek olarak tek bir `gpt-5.6-luna` alt ajanı yalnız kaynak raporu okuyarak öncelik ve kabul ölçütlerini değerlendirdi; kod doğrulaması yapmadı.

## 2. Rapora ilişkin mühendislik yargısı

| Konu | Değerlendirme | Plana etkisi |
| --- | --- | --- |
| B1: çok satırlı adım silme | Rapor somut kanonik/türev örnekleri sunuyor; genel bir parser eleştirisinden daha güçlü kanıt. Karar etkisi henüz ayrı bir soru. | Önce karakterizasyon; sonra sınırlandırılmış kaynak düzenlemesi ve yeni üretim sürümü. |
| B8: istem, hata ve bütçe | Gönderilen istemle kaydedilen kimliğin ayrılması ve hatanın triyaj kararına dönüşmesi, canlı sonuçların yorumunu doğrudan etkiler. | Canlı pilot öncesi zorunlu kapılar. Retry eklemek tek başına çözüm sayılmaz. |
| B10: ağırlık, ECE, tekrar | Ağırlık farkıyla sıfır davranış değişiminden pozitif sonuç çıkabilmesi güçlü analitik karşıörnek. ECE ve eksik tekrar bağımsız hata yolları. | Küçük bağımsız testlerle erken doğrulama; düzeltmeleri analiz sürümüyle yayımlama. |
| B11/B12: provenance ve config | Hash kaydetmek, ayarın uygulanmasını veya dosyaların birlikte tamamlanmasını sağlamaz. | Etkili girdi çözümü ve bundle bütünlüğü ayrı teslimler. |
| B2/B3: PRNG ve tahsis | Garanti açığı ile gözlenmiş nondeterminizm ayrılmış. Mevcut rotasyon sabit girdide deterministik olabilir. | Önce ortam/kök karşılaştırması; yeni PRNG veya yeniden tahsis yok. |
| B4/B6/B7: zincir ve evaluator | Gelecekteki özellik sınırı, baseline rolü ve mevcut bug aynı tür iş değildir. | Zincirleme ve evaluator iyileştirmesi bakım paketine eklenmez. |
| B9/P1: performans | Çağrı tekrarı kanıtı, süre darboğazı kanıtı değildir. Tekrar okuma ayrıca tutarlılık sorunudur. | Snapshot önce; worker havuzu ölçüm sonrasında koşullu. |

Raporun önceki brief'teki bazı teşhisleri açıkça reddetmesi önemli: `:02d` için 100'de taşma, smoke politikası fallback'i ve verilen CLI'de `max_cases=None` ile bütçe atlama iddiaları doğrudan iş listesine alınmamalı. Güncel kod doğrulaması bu düzeltmeleri de kapsamalı.

### İyileştirilmesi gereken noktalar

1. **Mimari kapsam küçültülmeli.** Tek koordinatör, retry, bütçe, kayıt, yayın ve analiz yapan büyük bir sınıf olmamalı. Ortak sözleşmeler ve küçük mevcut giriş noktası adaptasyonları yeterliyse orada durulmalı. Yeni framework veya genel amaçlı depolama sistemi gerekçelendirilmiş değil.
2. **Bağımlılıklar test hazırlığını engellememeli.** ECE ve paired susceptibility karşıörnekleri için tüm M1/M2 uygulamasını beklemek gerekmez. Nihai veri modeliyle entegrasyon daha sonra yapılabilir.
3. **Mühendislik ile bilimsel seçim ayrılmalı.** Kayıt bütünlüğü ve formül uygulama hataları doğrudan test edilebilir. Ana ağırlıklandırma, bağımsızlık varsayımı ve boyut hedeflerinin geçerliliği ayrıca karara bağlanmalıdır.
4. **Etki envanteri eksik.** B1'in toplam kaç türevi etkilediği, başarısızlıkların hangi tüketicilere girebildiği ve uygulanmayan ayarların tam listesi başlangıçta çıkarılmalı. Örnek vaka toplam etki sayısı değildir.
5. **Yayınlanabilirlik ile tamamlanmışlık ayrılmalı.** Hataları düzgün kaydedilmiş bir çalışma teknik olarak tamamlanmış bir bundle olabilir; bilimsel karşılaştırma için yeterli coverage sağlamamış olabilir. İki durum ayrı alanlarla taşınmalı.
6. **Performans eşiği tek başına yeterli değil.** Rapordaki %20 önerisi ölçülmüş kazanç değildir. İleride aynı ortamda tekrarlı süre ölçümü, değişkenlik ve ek bakım maliyetiyle birlikte değerlendirilmeli.

## 3. Çalışma sınırları

İlk tur değerlendirme ve plan üretimiydi; şimdi fazlı uygulama sürüyor. Güncel
tamamlanma durumu yukarıdaki tabloda, ayrıntılar kabul kayıtlarındadır. Kullanıcının
verdiği dizinler üzerinden her teslimin okuma kapsamı ayrıca daraltılır.

- Tarihsel `records`, `analysis`, raporlar ve türevlerin üzerine yazılmaz.
- Karakterizasyon sırasında mevcut seed, operatör sırası, vaka tahsisi, hedefler ve evaluator karar formülleri korunur.
- Yeni operatör, zincirleme, korpus büyütme ve hedef kalibrasyonu bu pakete dahil değildir.
- Canlı API kullanımı ve sağlayıcı deneyi bu planın hazırlanması kapsamında başlatılmaz.
- Offline hata testlerinde fake transport kullanılır; ağ erişimi testin başarı koşulu olamaz.
- Başarı alanı dışındaki değişiklikler ve eski şema desteği her teslimde açıkça belirtilir.

## 4. Teslim planı

Önerilen sıra: **E0 → E1 → E2 → E3 → E4 entegrasyonu → E5 düzeltmesi**. E4'ün analitik test hazırlığı ve E5'in mevcut davranış karakterizasyonu E0'dan sonra bağımsız ilerleyebilir. E6 koşulludur. Bu sıra her işin tek PR olması gerektiği anlamına gelmez.

### E0 — Referans ve bulgu doğrulama paketi

Bağ: G0; bütün B bulguları için başlangıç. Kapsam: küçük–orta, ortam erişimine bağlı.

Görev: [E0 görev dosyası](issue-05-E0-task.md). E0 yürütüldü ve kabul edildi.

- [x] HEAD, dirty kapsam, lock, interpreter ve paket sürümünü kaydet.
- [x] Eski artefaktların hash envanterini al; yerel commit/tag ilişkisini doğrula.
- [x] Rapor bulguları için güncel durum ve açık/ertelenmiş kanıt matrisini üret.
- [x] Aynı girdilerle iki yeni offline çalışma üret.
- [x] Dosya/alan karşılaştırma politikasını tanımla; helper kusurlarını kapat.
- [x] Yeni/yeni ve eski/yeni farklarını kaydet; açıklanmayan veri farkı yok.

Teslim: referans envanteri, bulgu matrisi ve diferansiyel sonuç raporu.

Kabul: yeni çalışmalarda açıklanmayan deterministik fark yok; eskiyle her fark kayıtlı. Tarihsel referans yeniden üretilemiyorsa arşiv korunur fakat doğrulanmış golden sayılmaz. Ortam eksikliği determinism hatası diye etiketlenmez.

### E1 — Uygulanan tarif ve değişmez vaka girdisi

Bağ: M1, G1/G2; B2/B3/B8/B9/B11/B12. Kapsam: orta.

- [ ] Config alanlarını `uygulanıyor / desteklenmiyor / yalnız metadata` olarak envanterle. Desteklenmeyen davranış isteğini çalıştırmadan önce reddet.
- [x] E1c/E1e: generation/analysis seed'leri, evaluator ayarları ve prompt kaynağını uygulanan kopyaya bağla.
- [ ] Rapor ve hedef içerik kimliklerini, vaka seçimini, evaluator tarifini ve analiz sürümünü ayrı bağla. İnsan-okunur `case_id` korunur.
- [x] E1b: build_cases sonrası metin/hedef snapshot'ını koru; legacy sınırı belgeli.
- [x] E1c: template ve render edilmiş prompt kimliğini ayır; bu tam HTTP payload hash'i değildir.
- [ ] Etiket erişimi ayrımı E2 evaluator/outcome sözleşmesine taşındı; oracle davranışı korunacak, mevcut hile iddiası yok.
- [x] E1d: farklı geçici köklerde aynı snapshot/target için aynı stimulus kimliği.

E1 kapanışı: unsupported config matrisi E1a'da, içerik/hedef/seçim kimlikleri
E1d'de, etkili generation/evaluator/analysis ayar bağı E1e'de tamamlandı.
Etiket yetkisi E2'ye, çapraz Python garantisi E6'ya aittir; bu sahiplik değişimi
işlerin tamamlandığı anlamına gelmez.

Kabul: kullanılan girdi/ayar ile kimliği ayrışamaz; unsupported config dispatch öncesi reddedilir; başarı yolundaki eski kararlar ve türev baytları E0'a göre değişmez. Evaluator karşılaştırmasında tüm recipe eşitliği değil, stimulus/hedef/seçim uyumu aranır.

### E2 — Outcome, tekrar ve fiziksel istek bütçesi

Bağ: M2'nin yürütme kısmı, G3; B8/B9 ve B10'un coverage kısmı. Kapsam: orta–yüksek.

Görevler: [E2a](issue-05-E2a-task.md) ve son
[E2b-r2](reviews/issue-05/E2b-r2-acceptance.md) kabul edildi; E2 kapandı.

- [x] E2a: başarı, başarısızlık ve çalıştırılmama durumlarını ayrı temsil et; geçerli model kararı yalnız başarıda bulunsun.
- [x] E2b: Planlanan iş, tamamlanan iş, skorlanabilir gözlem ve fiziksel attempt sayaçlarını tanımla. Sayaçların toplamları ledger ile uzlaşmalı.
- [x] E2b-r2: Her fiziksel dispatch öncesi bütçeyi tek sahipte rezerve et. Başka client cap'iyle doğrudan giriş de bu sınırı aşamasın.
- [x] E2b: Parse, transport, timeout, provider ve bütçe hatalarını ayır; terminal yerel hatayı retry etme.
- [x] E2b-r2: Request timeout, toplam deadline, minimum aralık ve `Retry-After` davranışını ayrı test et. Bekleme deadline'a sığmıyorsa kontrollü terminal sonuç üret.
- [x] E2a/E2b: Severity dönüşümü, JSON kabul politikası ve canonical/derived kayıt aktarımını fake cevaplarla doğrula.
- [x] E2a/E2b: Eksik veya başarısız tekrarları tam tekrar birliği gibi raporlama. Seçim ve tekrar kimlikleri tekil olmalı.

Kabul: sıfır canlı istekle bütün hata senaryoları kapanır; fiziksel cap aşılmaz; failed outcome karar doğruluğuna, ECE'ye veya geçerli karar birliğine giremez. Başarılı gözlemlerde hesaplanan oranlar coverage ile birlikte sunulur.

### E3 — Sonuç paketinin bütünlüğü ve okuyucu sözleşmesi

Bağ: M2'nin yayın kısmı, G6; B11 ve U11. Kapsam: orta.

- [x] E3a: Bütün bundle yazıcı ve okuyucularını envanterle; CLI `compare` ve cache edilmiş metrik tüketimini dahil et.
- [x] E3a: Yeni çalışma dizininde tüm dosyalar/hash'ler tamamlanmadan bundle'ı tamamlandı diye görünür kılma. Aynı dosya sistemi ve taşıma davranışı varsayımlarını belirt.
- [x] E3a: Her yazım sınırında kesinti testleri ekle; eksik, karışmış, stale veya hash'i uyuşmayan paketleri okuyucular reddetsin.
- [x] E3b: Her materialization planını written, no-op, duplicate, safety-blocked veya error durumlarından biriyle kaydet; popülasyon değişimi sessiz kalmasın.
- [x] E3b-r1: Eski şemayı açık legacy okuma yolu ile destekle veya açıklayıcı hata ver; tarihsel arşivi otomatik dönüştürme.

Kabul: tek dosyada rename başarılı olması yeterli sayılmaz; bütün okuyucular aynı tamamlanma/bütünlük sınırını uygular. Paket bütünlüğü ile benchmark coverage yeterliliği ayrı raporlanır.

### E4 — Sürümlü ölçüm ve doğrulanmış analiz

Bağ: M3, G5; B5/B6/B7/B10/B11 ve U12. Kapsam: orta; bilimsel seçimler ayrı.

- [x] E4a: Metrik başına uygunluk, pay/payda, eksik veri, sıfır payda, ağırlık ve analiz birimi sözleşmesini yaz.
- [x] E4a: Eşit parent/child kararları ve eşit olmayan child sayılarıyla paired susceptibility'nin sıfır olduğunu bağımsız küçük örnekte sınayarak başla.
- [x] E4a: ECE için `0.95/doğru` ve `1.0/yanlış` son-bin örneğinde beklenen `0.475` değerini test et; her uygun kaydın tam bir bine girdiğini doğrula.
- [x] E4a: `correct` değerinin hesaplanan kararla tutarlılığını, kayıt tekilliğini ve seçim kapsamını okuyucuda denetle.
- [x] E4a: Parent bağları ve sunum çiftlerinin mantıksal bağını taşı; tekrar kapsamını planlanan repeat sayısına göre doğrula.
- [x] E4b-r1: Parent gerektiren alt grup metriklerine gereken eşleşme bağlamını sağla; uygun olmayan metriği neden belirtilmiş biçimde tanımsız bırak.
- [x] E4b: Mevcut operatörler için ölçüm uygunluğu tablosu hazırla; karar değişmezliğini kalite nötrlüğüyle eşitleme. Boyut hedeflerinin authored niteliğini belirt.
- [x] E4b: Eski ham kayıtlar üzerinde bağımsız yeniden hesaplama yap; yeni analiz ile legacy değerleri fark ve neden tablosunda göster.
- [x] E4b-r1: Analiz çıktısını kayıt hash'i ve analiz tanım sürümüne bağla; eski `analysis.json` üzerine yazma.

Kabul: analitik karşıörnekler geçer; eski ham kararlar ve hedefler değişmez; güncel analiz farkları sürümlenmiş ve açıklanmıştır. Yeni bootstrap yöntemi, genel geçerlilik veya 52 bağımsız örneklem iddiası bu kapının otomatik sonucu değildir.

### E5 — Kaynak koruyan düzenleme ve B1 düzeltmesi

Bağ: M4, G4; B1/B4. Kapsam: orta.

- [x] E5a: mevcut dönüşümleri karakterize et; kaynak aralığı, belge sürümü ve düzenleme önkoşulunu davranış değiştirmeden belirginleştir.
- [x] E5b: çok satırlı liste öğesinin tam aralığını işle; rapordaki üç örneği ve toplam etkilenen türev envanterini doğrula.
- [x] Fence türü/uzunluğu, devam paragrafı, UTF-8 ve satır sonları için desteklenen biçim profilini test et; belirsiz girdide kontrollü ret/no-op davranışını tanımla.
- [x] E5b-r1: eski belge konumlarını yeni belge sürümüne uygulamayı reddet; tek adımlı parent sınırını koru.
- [x] Düzeltmeyi ayrı üretim sürümüne çıkar; metin farkı, vaka sayısı, kararlar ve metriklerdeki etkiyi raporla.

Kabul: E5a'da açıklanmayan bayt farkı sıfır; E5b'de hedeflenen öğe tam düzenlenir, yetkili aralık dışındaki kaynak korunur. Eski türevler korunur. Üretim ve analiz etkileri ayrı deneylerle karşılaştırılır; mümkünse eski/yeni veri × eski/yeni analiz matrisi kullanılır.

### E6 — Ortam garantisi ve koşullu performans

Bağ: G1/G7, P1. Kapsam: ölçüme bağlı.

- [ ] Desteklenen interpreter ortamları ve iki farklı kökte deterministik artefakt karşılaştırması yap; değişken metadata politikasını önceden sabitle.
- [ ] Materialization, parse/load, evaluator, analiz ve yazım sürelerini ölç.
- [ ] Yalnız anlamlı darboğaz varsa worker havuzunu değerlendir; evaluator durumunu, config/vaka sırasını ve bootstrap akışını koru.

Kabul: ortam garantisi yalnız test edilen kapsam için verilir. Paralellik ancak tekrarlı toplam süre ölçümlerinde gerekçeli kazanç ve deterministik veri eşitliği birlikte sağlanırsa alınır. %20 başlangıç önerisidir, taahhüt değildir.

## 5. Bilimsel kararlar ve pilot kapısı

Bu kararlar planı yazmayı veya bağımsız mühendislik testlerini engellemez. İlgili analiz/pilot uygulamasından önce kayıt altına alınmalıdır.

| Karar | Önerilen başlangıç yaklaşımı | Beklediği aşama |
| --- | --- | --- |
| Tarihsel koruma | Eski artefaktlar değişmez; düzeltilmiş analiz ve üretim ayrı sürümlenir. | E0'dan itibaren uygulama ilkesi. |
| Ana estimand | Mevcut case-weighted betimsel ölçüyü başlangıç karşılaştırması olarak tut; parent-eşit ağırlığı ayrı bilimsel seçim olarak değerlendir. Henüz kabul edilmiş nihai tercih değildir. | E4 yeni analiz yayını. |
| Bağımlılık ve CI | Parent/pair ilişkisini önce kaydet; bootstrap yöntemini bilimsel protokolde gerekçelendir. | Yeni belirsizlik sonuçları. |
| Yeniden üretim ortamı | Bir referans ortam seç; paket desteği ile bayt eşitliği iddiasını ayrı yaz. | E0 referansı ve E6 garanti kapsamı. |
| Pilot bütçesi | Hard fiziksel istek cap'i korunur; seçim büyüklüğü, retry ve tamamlanma hedefi birlikte çözülür. | Canlı pilot. |
| Boyut hedefleri | Mevcut authored hedefleri değiştirme; insan yargısıyla kalibrasyonu bilimsel çalışma olarak ayır. | Yeni hedef sürümü. |

Rapordaki örnek plan 60 vaka × 3 tekrar = 180 ilk attempt gerektiriyor. Her gözlem için iki ek retry hakkı varsa en kötü durum 540 attempt'tir. 180 cap ile tam kapsam ve bütün retry hakları aynı anda garanti edilemez. Bu aritmetik bir kapasite kısıtıdır; çözüm cap'i sessiz artırmak değil, pilot tasarımını açıkça seçmektir.

Canonical pilot için E0–E4'ün ilgili kapıları kapanmalı; türevli pilot ayrıca E5'i gerektirir. Gerçek sağlayıcı davranışı, gecikme ve maliyet hakkında mevcut rapordan sonuç çıkarılmaz.

## 6. Bağlam ve model bütçesiyle çalışma protokolü

Her sonraki tur bir teslim ve kullanıcının verdiği dizinlerle sınırlandırılır. Ana ajan kapsamı, kararları ve entegrasyonu sahiplenir. Luna yalnız bağımsız ve sınırlı görevde kullanılır: örneğin belirli testlerin kapsama incelemesi veya küçük bir dosya grubunun bulgu eşlemesi. Aynı geniş tarama iki ajana verilmez.

Her teslim sonunda kısa bir kayıt tutulur: incelenen dosyalar, doğrulanan/çürütülen bulgular, yapılan değişiklikler, test sonucu, artefakt farkları ve sıradaki açık karar. Model seçimi veya token bütçesi, doğrulanmamış işi tamamlanmış göstermeye gerekçe değildir.

İlk uygulama oturumunun önerilen kapsamı **E0**'dır. Çıktısı bir kod refactor'ı değil, hangi referansa ve hangi güncel bulgulara göre ilerleyeceğimizi belirleyen doğrulama paketidir.
