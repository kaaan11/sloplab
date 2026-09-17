# E1d — Vaka girdisi, hedef ve seçim kimlikleri

Durum: Hazır; henüz uygulanmadı. Yürütücü: Luna. Kök: `/home/kaan/sloplab`.
Önkoşul: [E1c kabul kararı](reviews/issue-05/E1c-acceptance.md).

## Amaç ve tek teslim sınırı

E1b raporu bellekte sabitledi; fakat aynı case_id altında farklı metin veya hedef
bulunmasını deneyler arasında ayıran içerik kimliği yok. Bu pakette deterministik
study için **kullanılan snapshot'lardan türetilmiş, yol bağımsız bir girdi kimlik
dosyası** üret. Mevcut case_id, seed/tahsis, kayıt ve analiz davranışı korunacak.

Tam etkili yürütme tarifi, evaluator kaynak kodu hash'i, ortam kilidi, analiz
tanımı, reader doğrulama/migration, atomic bundle ve pilot entegrasyonu bu
paketin dışında. Yeni dosya bütün provenance sorunlarını çözmüş sayılmaz.

## Okuma ve değişiklik kapsamı

AGENTS.md yönergelerini oku. Ardından harness.py (SuiteCase/build_cases/case_document),
experiments/study.py, experiments/runner.py, models/report.py ve models/run.py,
CLI study yolu, ilgili study/preflight/snapshot testleri yeterlidir. Yeni küçük
bir `experiments/input_identity.py` modülü tercih edilebilir. Bilimsel raporları,
tüm korpusu sohbet bağlamına veya başka projeleri tarama; alt ajan kullanma.

İzinli: kimlik helper/modülü, deterministik study bağlantısı, ilgili testler ve
kısa şema belgesi. Mevcut records/manifest şemasını değiştirme; pilot veya
evaluator'a kimlik alanı aktarma. Yeni dosya evaluator-visible input değildir.

## Önceden belirlenmiş kimlik sözleşmesi

Yeni dosya adı: `input-identity.json`; `schema_version` sabit `1`.

Her vaka satırı şu bilgileri taşımalı:

- Mevcut `case_id`, `case_kind`, `parent_id`, `operator`, `report_class`, `seed`.
- `report_hash`: snapshot ReportDocument.raw_text'i taşıyan
  `{"domain":"sloplab.input","type":"report","version":1,"text":raw_text}`
  nesnesinin aşağıdaki deterministik UTF-8 JSON serileştirmesinden SHA-256.
  İnceleme açıklaması (2026-09-09): ilk görev metnindeki doğrudan metin hash'i
  ifadesi ile bütün hash nesnelerinde domain/version isteği çelişiyordu;
  sürümlü nesne seçimi kabul edildi. Bu plain-text SHA-256 değildir.
- `target_hash`: expected_decision ve expected_dimensions içeriğini bağlayan
  sürümlü nesnenin SHA-256'sı.
- `input_hash`: report_hash ve target_hash'i bağlayan sürümlü nesnenin SHA-256'sı.

Dosya ayrıca **sıralı** case_id listesini bağlayan `selection_hash` ve sıralı
vaka satırlarını (kimlik/parent/operator/class/seed dahil) bağlayan `inputs_hash`
taşımalı. Bütün hash nesneleri açık domain/type + version içersin; birbirinden
farklı nesne türleri yanlışlıkla aynı kimlik alanına dönüşmesin. Hash'ler tam
64 lowercase hex olarak kaydedilmeli. Alan isimlerini uygulamada değiştirme.

JSON tabanlı hash nesnelerinde `sort_keys=True`, açık separators, UTF-8,
`ensure_ascii=False`, `allow_nan=False` kullan; serializer sözleşmesini belgeye
yaz. Bu, bütün diller/gelecek Python sürümleri için standart canonical JSON
garantisi değildir. Kimlik karşılaştırması desteklenen şema/sürümle sınırlıdır.
Dict anahtar sırası hash'i etkilemez; vaka sırası etkiler. Eksik boyut ve 0.5
aynı hedef değildir; None ile karar string'ini ayrı koru.

`report_hash` disk dosyasının ham hash'i değildir: parser'a verilen ve evaluator'ın
gördüğü raw_text'in kimliğidir. Parser satır sonunu normalize etmişse bunu disk
bayt eşitliği diye sunma. Render edilmiş LLM prompt hash'iyle de karıştırma.

Mutlak corpus/out dizini, ReportDocument.path, timestamp, run_id, git HEAD,
evaluator adı/versiyonu ve karar çıktısı bu girdi kimliklerine dahil edilmez.
İki evaluator'ın aynı girdide karşılaştırılması farklı evaluator kimlikleri
yüzünden engellenmemeli. Kaynak kodu/ortam kimliği sonraki recipe paketidir.

## Study bağlantısı

`build_cases` tamamlanınca ve ilk evaluator çalışmadan önce kimlik nesnesini
aynı cases listesinden üret. Snapshot'ı eksik vakayı bu yeni kimlik helper'ında
kontrollü reddet; legacy disk fallback'ini hash üretimi için kullanma. Metin,
manifest veya hedef için yeniden disk okuma yapma. Target dict'ini kopyalayarak
hash girdisini sabitle; bu tam in-process immutability iddiası değildir.

Başarılı çalışmanın çıktısına input-identity.json dosyasını ekle. Yazım yerini
mevcut akışa küçük bir bağlantıyla seç; E3'ün atomik yayın protokolünü burada
tasarlama. Kimlik nesnesini çalışma sonunda mutable kaynaklardan tekrar üretme.
E1a preflight retleri hiçbir output üretmeme davranışını korumalı.

## Kabul testleri

1. Aynı snapshot/target/sıra aynı kimlikleri üretir; target dict key sırası farkı
   etkisizdir. Her hash'i testte bağımsız tanımlanan nesneden yeniden hesapla.
2. Aynı case_id ile yalnız raw_text değişirse report_hash, input_hash ve
   inputs_hash değişir; target_hash ve selection_hash aynı kalır.
3. Yalnız bir target değeri veya expected_decision değişirse target_hash,
   input_hash ve inputs_hash değişir; report_hash ve selection_hash aynı kalır.
4. Eksik boyut ile açık 0.5 farklı target_hash üretir. NaN/Infinity sessizce
   serileştirilmez; anlaşılır doğrulama hatası olur.
5. Vaka sırası değişirse selection_hash/inputs_hash değişir. Aynı sıra ve girdide
   yalnız evaluator listesi değişmesi input kimliklerini değiştirmez.
6. Özdeş dosyalarla iki farklı geçici korpus/output kökünde build edilmiş
   snapshot'lar aynı kimliği verir. Path alanını hash'ten çıkardığını yalnız
   implementation assert'iyle değil bu gerçek geçici kök örneğiyle doğrula.
7. Build sonrası disk değişimi hash nesnesini etkilemez; helper loader'a
   dokunmaz. Boş snapshot'ta açık ret olur. R04/preflight regresyonları geçer.
8. Başarılı study dosyası vaka/kayıt sırasıyla uyumludur; vakalar evaluator
   sayısı kadar çoğaltılmaz. E0'da 297 vaka, 594 kayıt ayrımını koru.

## Veri eşdeğerliği ve yeni dosya politikası

Bu pakette **tek kasıtlı çıktı farkı input-identity.json dosyasının eklenmesidir**.
480 dosyalık E0 referansına karşı yeni kümenin tam olarak bu dosyayı eklediğini
göster; diğer dosyaları atlama. Eski 479 veri/index dosyası ham aynı kalmalı;
manifestoda aynı ortam/kök koşulunda yalnız zaman alanları farklı olabilir.
Yeni dosyanın hash'ini ve iç bağlarını ayrıca doğrula.

E0 compare helper'ı tam küme eşitliği istediğinden ek dosyayı reddetmesi beklenir;
eski helper/allowlist'i değiştirme. Yeni faza özel karşılaştırma helper'ı
kullanıyorsan kaynağını teslim et ve yalnız bu tek ek dosyaya izin ver. Başka
eksik/ek dosya veya karar/hedef/metrik farkı kabul edilmez. Golden güncelleme yok.

## Çalışma ve teslim disiplini

E1a/E1b/E1c dirty değişikliklerini koru. Kod değişiminden **önce** dokunulacak ve
korunacak dosyaların hash'lerini programatik kaydet; çıktı dosyalarını gerçekten
teslim dizinine yaz. Untracked testler git diff'te görünmez; ayrıca listele.
Başlangıç kaydı atlanırsa sonradan oluşturup başlangıç diye adlandırma.

Hedefli testler ve ilgili study/snapshot/preflight/CLI testleri, değişen dosyalarda
lint/format/type kontrolleri ve bir yeni offline study yeterlidir. Zorunlu repo
yönergelerini uygula; aynı kontrolleri yeni neden olmadan tekrarlama. Canlı API,
ağdan kurulum, lock/YAML/korpus/eski artefakt değişikliği veya commit/push yok.

Teslim: `docs/reviews/issue-05/E1d/` (doluysa yeni kardeş). README, schema-contract.md,
gerçek commands.jsonl + stdout/stderr/exit, başlangıç/bitiş hash'leri, bağımsız
E1d diff'i ve yeni test listesi, comparisons.md, output hash envanteri. Büyük
run için yeni `/tmp/sloplab-e1d-XXXXXX/` kullan; kalıcı arşiv garantisi verme.

Bitince dur; E1d durumunu yaz. Sonraki paket etkili recipe/seed/config kimliğidir;
bu işte E1'in tamamını kapandı veya bütün okuyucuları doğrulanmış ilan etme.
