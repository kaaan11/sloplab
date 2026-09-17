# E1e — Etkili deney tarifini bağla, E1'i kapat

Durum: Hazır, uygulanmadı. Kök: `/home/kaan/sloplab`. Yürütücü: Luna.
Önkoşul: [E1d kabulü](reviews/issue-05/E1d-acceptance.md).

## Tek paket hedefi

E1a desteklenmeyen ayarları reddetti; E1b vaka snapshot'ını, E1c prompt kimliğini,
E1d metin/hedef/seçim kimliğini bağladı. Kalan E1 işi, deterministik study'nin
**gerçekte uyguladığı generation/evaluation/analysis ayarlarını bir kez çözmek,
aynı çözümü çalıştırmak ve kaydetmektir**. Bu paketi yeni harfli alt fazlara
kendiliğinden bölme; gerekli doğrudan bağlantıları birlikte tamamla.

E1 sonunda kayıtlı girdi kimliği ile uygulanan ayarlar açık olacak. Etiket erişim
yetkisi E2, reader/bundle doğrulama E3, metrik semantiği E4, kaynak düzenleme E5,
çapraz ortam byte garantisi E6 sorumluluğundadır. Bu işleri burada kapandı sayma.

## Kapsam

Geçerli AGENTS.md yönergelerini oku. Okuma/değişiklik: experiments config/study/
runner/input_identity, CLI study, evaluator registry, suite modeli/materializer
çağrı sözleşmesi ve ilgili tests. Küçük bir resolved recipe modülü eklenebilir.
Evaluator formülleri, materyalizer algoritması, scoring hesapları, LLM/pilot
protokolü ve bilimsel raporlar kapsam dışıdır. Yeni framework/PRNG/factory yok.

## Çözülmüş tarif sözleşmesi

Çalışma başında mevcut preflight, yol çözümü ve suite yüklemesi bir sınırda
tamamlansın. Aşağıdaki efektif girdilerin kopyasını/sabit temsilini al:

- Suite'in uygulanan generation seed'i, canonical dahil etme seçeneği ve mevcut
  sıralı politika/operatör listeleri. Sıraları değiştirme.
- Çalışmada gerçekten kullanılacak çözümlenmiş corpus_root ve suite dosyası yolu.
- Sıralı evaluator nesneleri, bunların gerçek name/version değerleri ve kabul
  edilmiş boş config'leri. İsimleri tekrar çalışma döngüsünde registry'den çözme;
  aynı çözümlenmiş nesneleri kullan. Thread/process güvenliği iddia etme.
- Analysis bootstrap seed'i (study.base_seed), resamples, ci ve kabul edilmiş
  analysis bayrakları. Study seed ve generation seed ayrı isimlerle kaydedilsin;
  farklı olmaları hata değildir ve üretim seçimlerini değiştirmez.
- repeat_index ve uygulanmış provenance seçenekleri. CLI analizine gerek duyulan
  ayarlar da bu kopyadan gelsin; çalışma sonunda mutable orijinal config'e dönme.

Frozen dataclass içinde mutable dict tutmak tek başına freeze değildir. Küçük
immutable tuple/JSON temsili veya sınırda kontrollü deep copy kullan; kapsamlı
model göçü yapma. Tarifte kayıtlı ayarla kullanılan ayarın ayrışamayacağını test et.
Yüklenen suite aynı nesneden/kopyadan materializer'a verilsin; recipe üretimi için
dosya tekrar okunmasın. Mevcut path resolution önceliği sessizce değiştirilmesin.

Doğrudan `run_deterministic_study` çağrısı kayıt/materialization yapar; CLI ayrıca
analiz üretir. API'nin üretmediği analizi ürettiği iddia edilmesin. Config'teki
analysis talebi ile fiilen tamamlanan aşama farklıdır. Doğrudan API ve CLI aynı
çözümleme sınırını kullansın; mevcut public çağrı imzası mümkün olduğunca korunsun.

## Yeni çıktı ve kimlikler

Yeni `execution-recipe.json`, `schema_version: 1` dosyası ekle. Mevcut
records/analysis/manifest ve input-identity şemasını değiştirme.

Bu dosyada generation, evaluation, analysis bölümleri ve ayrı hash'leri olsun;
hash nesneleri domain/type/version içersin, E1d JSON encoding kuralını kullansın.
Analysis bölümü algoritmanın bilimsel geçerliliğini değil uygulanan seçenekleri
tanımlar. Generation/evaluation/analysis hash'lerini bağlayan settings_hash olsun.

E1d `inputs_hash` ve `selection_hash` değerlerini aynı in-memory identity
nesnesinden bu dosyaya bağla; dosyayı sonradan tekrar okuyup yeni kimlik üretme.
Bu iki girdi kimliği + settings_hash için `execution_hash` kaydet.

Mutlak yolları `locations` gibi hash kapsamı dışında açık bir alanda tut.
Aynı metin/etiket/politika/ayarlar farklı kökte taşındığında semantik kimlikler
aynı kalmalı; location alanları değişebilir. Çözümlenmiş suite hash nesnesine
corpus_root/path dahil etme; uygulanan root ve içerik kimliği ayrı taşınır.

Kod/ortam provenance'ını aynı dosyada ayrı metadata olarak kaydet: mevcut HEAD,
dirty göstergesi, kullanılan Python implementation/version ve paket versiyonu,
mevcutsa lock dosyasının SHA-256'sı. Bunlar settings_hash'e karışmasın. Dirty HEAD
tam kod kimliği değildir; böyle sunma. Tam source dependency closure veya provider
determinism garantisi bu metadata'dan çıkarılamaz. Shell/environment dökümü veya
credential kaydı yapma. Mevcut version alanlarını değiştirme.

Dosyadaki alan adları ve her hash'in girdilerini önce `recipe-contract.md` içinde
yaz; sonra aynı sözleşmeyle uygulama/test üret. Paket içinde rutin isim tercihleri
için onay isteme. Bağlamı büyüten genel mimari tasarlama.

## Kabul testleri

1. Varsayılan config için gerçekten kullanılan generation seed, evaluator
   nesneleri ve CLI bootstrap parametreleri tariftekiyle eşit (spy ile göster).
2. Farklı generation/analysis seed'leri ayrı kaydedilir; bootstrap seed değişimi
   generation hash'ini değiştirmez. Mevcut mutation dağılımını koru.
3. Çözümleme sonrası orijinal config, suite dosyası veya registry kaydı değişirse
   bu koşu kullanılan ayarı/nesneyi ve kayıtlı tarifi değiştirmez. Snapshot sonrası
   değişimi geçici fixture/monkeypatch ile sınırla; tüm eşzamanlılık garantisi iddia etme.
4. Evaluator listesi/sırası değişince evaluation/settings/execution kimlikleri
   değişir; inputs_hash ve selection_hash aynı vaka girdilerinde sabit kalır.
5. Bootstrap ayarı değişince analysis/settings/execution hash'i değişir; input
   kimlikleri ve generation/evaluation bölümleri değişmez.
6. İki geçici kökte aynı semantik girdiler aynı semantik hash'leri verir; location
   metadata'sı farklı olabilir. Dict key sırası etkisiz, operator listesi sırası etkili.
7. Bütün hash'leri uygulama hash fonksiyonunu çağırmadan bağımsız yeniden hesapla.
8. E1a retleri hâlâ output öncesinde; E1b/c/d davranışları gerilememiş. API/CLI
   farkında gerçekleşmeyen analiz aşaması başarılı tamamlandı gibi kaydedilmez.

## Eşdeğerlik ve kapanış

Yeni bir offline deterministik study üret. Referans E1d
`/tmp/sloplab-e1d-jJOgHz/run`: eklenen tek dosya execution-recipe.json olmalı;
input-identity.json ve eski 479 veri/index dosyası ham aynı kalmalı. Eski manifestoda
yalnız zaman farkı beklenir. Yeni dosyanın location/ortam alanlarını ve hash bağlarını
ayrı doğrula. E0/E1d helper'ını genişletme; faza özel karşılaştırma kodunu teslim et.

Hedefli testler + ilgili CLI/study/preflight/snapshot/prompt/identity testlerini ve
değişen dosyalarda lint/format/type kontrollerini çalıştır. E1 kapanışında bir tam
offline test paketi çalıştır; ardından yeni gerekçe olmadan tekrar koşma.

Teslim: `docs/reviews/issue-05/E1e/` (doluysa yeni kardeş): README, recipe-contract.md,
commands.jsonl, kalıcı test/stdout/stderr/gerçek exit kayıtları, comparisons.md,
run hash envanteri, E1e'ye özgü diff ve yeni dosya listesi. Başlangıç/bitiş hash'leri
araçla üretilip gerçekten dosyaya yazılmalı; eski dirty/untracked işler korunmalı.
Canlı API, ağ kurulumu, eski artefakt/config/lock değişikliği, commit/push yok.

README sonunda E1a–E1e kapanış matrisi ve E2/E3/E4/E6'ya devredilmiş açık maddeler
bulunsun. E1 tamamlandı önerisini ana inceleyiciye sun; E2'ye kendiliğinden geçme.
