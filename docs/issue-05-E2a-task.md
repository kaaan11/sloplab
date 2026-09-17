# E2a — Başarısız LLM yürütmesini karardan ayır, etiket erişimini sınırla

Durum: Ana inceleyici düzeltmesiyle kabul edildi. Kök: `/home/kaan/sloplab`.
Yürütücü: Luna; kabul: [E2a kabul kaydı](reviews/issue-05/E2a-acceptance.md).
Önkoşul: [E1 kapanışı](reviews/issue-05/E1e-acceptance.md).

## Tek paket hedefi

LLM adapter'ın başarısız çağrı sonunda ürettiği needs_manual_review/sıfır güven/
sentetik boyut sonucu gerçek karar değildir. Yeni çalışmalarda bu sonuç hiçbir
CaseRecord başarı kaydına dönüşmemeli. Operasyonel sonuç ve skorlanabilir karar
ayrı temsil edilmeli; başarısız işler kayıttan sessizce kaybolmamalı.

Bu paket yeni LLM/pilot sonucu ve evaluator etiket sınırını kapsar. Bütçe rezervasyon
sahipliği, deadline/Retry-After, tam tekrar stabilitesi E2b; eski bundle okuma/
migration ve ortak yayın koordinasyonu E3; metrik formülleri E4 kapsamındadır.
Deterministik evaluator exception'ında bütün study'yi durdurma davranışının genel
izolasyona dönüştürülmesi E3'teki ortak koordinatöre aittir; burada yanlış karara
çevirme yapılmaz. Bu sınırları kapanışta açıkça yaz.

## Okuma/değişiklik kapsamı

AGENTS.md yönergelerini oku. İlgili alanlar: evaluators/llm/adapter.py,
evaluators/base.py ve oracle.py, models/evaluation.py ve run.py, scoring/harness.py,
experiments/pilot.py, scripts/llm_bench.py ve bunların mevcut testleri. Küçük bir
ortak typed failure modeli/modülü eklenebilir. Önce pilotun sayaç/sonuç tüketicilerini
`rg` ile bul; config/budget algoritmasını değiştirmeden bağlantıları tamamla.

Eski kabul edilmiş E1a–E1e kodunu koru. Bilimsel raporlar, yeni framework,
provider entegrasyonu veya corpus değişikliği yok; alt ajan başlatma.

## Başarı ve failure sözleşmesi

Başarıda `Evaluator.evaluate` mevcut EvaluationResult döndürmeye devam etsin.
LLM retry'ları bittikten sonra typed `EvaluationFailure` (veya eşdeğer açık ad)
yükseltsin; içinde karar/confidence/dimensions bulunmasın. En az hata türü,
mantıksal adapter attempt sayısı ve rendered_prompt_hash taşısın. Attempt sayısı
fiziksel gönderim sayısı diye sunulmasın; bu ayrım E2b'de merkezileşecek.

Parse, timeout ve diğer transport hata türlerini ayır. Raw model cevabı, tam
prompt, credential veya exception içeriğinin denetimsiz kopyası yeni ledger'a
yazılmasın; kontrollü kısa hata açıklaması/kodu yeterli. Retry/budget politikasını
bu fazda iyileştirmeye girişme; yerel BudgetExhausted türü varsa onu transport
arıza gibi tanımlama, açık bütçe türüyle kaydet. Tekrar deneme yetkisi E2b'dir.

`_failed_result` ile sentetik review üretimini kaldır. Success-path prompt hash'i
ve frozen template davranışı korunmalı. Content parser/severity düzeltmesi
yapma; bu faz için zorunlu olmayan temizliği ayrı not et.

`run_case` veya pilot, legacy bir evaluator'ın metadata.failed=True sonucu
döndürmesi halinde bunu da başarı kaydına çevirmesin: ortak failure sınırında
reddet/typed failure'a dönüştür. Eski arşivlerdeki başarısız kayıtlar değiştirilmez;
legacy dosya okuma politikası E3/E4'te açıkça ele alınacak.

## Pilot sonuç defteri ve kapsam

Pilot typed failure'ı vaka/tekrar sınırında yakalasın; beklenmeyen bütün program
hatalarını geniş catch ile sessizce yutma. Başarılar mevcut records.jsonl'ye
CaseRecord olarak yazılır, başarısızlıklar bu dosyada karar satırı olmaz.

Yeni `outcomes.jsonl`, `schema_version: 1` ile planlanan her `(case_id,
evaluator_name, repeat_index)` için tek satır taşısın. Durumlar `success`,
`failed`, `not_run`. Başarı satırı success record anahtarına referans verir;
failure satırı hata türü/adapter attempt bilgisi/rendered hash taşır, karar
alanı taşımaz. Bütçe nedeniyle başlamayan plan not_run ve açık nedenle kaydedilir.
Tam tekrar sonucunu veya budget algoritmasını değiştirmeden mevcut seçilen
popülasyonu deftere bağla. Tekil anahtarlar ve sıra açık olmalı.

Manifestoya ayrı `planned`, `successful`, `failed`, `not_run`, `scored` sayıları
ekle. `planned = successful + failed + not_run`; `scored = successful`.
Mevcut request/error/timeout sayaçlarını fiziksel client sayaçları olarak koru.
PilotRunResult ve script tüketicilerinde evaluations_attempted gibi mevcut
alanların anlamını açıkça belirt; başarısızlıklar çıkınca bu sayıyı records satır
sayısına eşitleme. Bütün işler başarısızken boş records dosyası + tam ledger geçerli
teknik sonuçtur; başarılı model ölçümü veya tamamlanmış benchmark diye sunulmaz.

Stability'ye failure kararı sokma. E2b kapsam denetimi tamamlanana kadar eksik
başarı tekrarları varsa stability'yi hesaplamayıp açık neden/coverage ver;
yalnız mevcut repeat_stability'nin union davranışına güvenme. Tam başarı repeat
yolunun mevcut değerleri korunur. Ledger atomikliği henüz E3 garantisi değildir.

## Etiket yetkisi

Oracle'ın etiket ihtiyacını açık bir capability ile belirt (ör. requires_labels).
Default capability False olsun. Harness, yalnız bu capability'yi açıkça bildiren
evaluator'a ground-truth kopyası versin; content-based evaluator'ların labels
alanı boş olmalı. Oracle davranışı ve kayıtların ground-truth alanları korunur.
Evaluator'a case/path kimliği sızdıran yeni erişim ekleme; E1b R04 testleri geçsin.

Pilot LLM'e expected_decision etiketi vermesin. Bu, Python içindeki kasıtlı erişimi
engelleyen sandbox değildir; normal evaluator API'sinin veri minimizasyonudur.
Spy testleri sırf eski etiket paylaşımını beklediği için kırılırsa gerçekten
etiket tüketen test evaluator'ına capability ekle; gerçek content evaluator'ları
etiket ihtiyacı varmış gibi işaretleyerek testi geçirme.

## Kabul testleri

1. Beklenen kararı review olan vakada timeout/parse failure accuracy başarısına
   dönüşmez. Typed failure ve ledger'da karar alanı bulunmadığını doğrula.
2. Başarı/failure/not_run karışımında her plan bir outcome üretir; sayaç denklemi
   ve success record referansları doğru. Tümü başarısız durum ayrı testtir.
3. Retry sonrası başarı ile kalıcı failure prompt hash/attempt kayıtları doğru;
   E1c template freeze ve aynı client sayaçları korunur. Fake transport kullan.
4. Legacy metadata.failed sonucu yeni CaseRecord'a giremez. Beklenmeyen program
   hatası anlamını korur; config hatası model failure'ı gibi kaydedilmez.
5. Eksik başarılı repeat'ler stability'de unanimous sayılmaz; raporda eksiklik
   görünür. Tam başarı yolunda önceki stabilite sonucu aynı kalır.
6. Content evaluator labels boş görür; oracle opt-in ile etiketi alır, aynı kararları
   üretir. Etiket kopyası mutasyonu hedefleri veya sonraki evaluator'ı etkilemez.
7. Script ve doğrudan pilot aynı result/ledger muhasebesini kullanır. Hiç gerçek
   API isteği yok; mevcut opt-in sınırı korunur.

## Doğrulama, eşdeğerlik, teslim

Hedefli failure/labels ve ilgili adapter/pilot/script/snapshot/prompt/R04 testleri,
değişen dosyalarda lint/format/type kontrolleri gerekir. Kabul öncesi tam offline
test paketini bir kez çalıştır. Mevcut başarısızlık-placeholder testlerini yeni
sözleşmeye göre değiştir; assertions'ı kaldırarak veya genel exception bekleyerek
geçirme. Kod düzenlemesinde mevcutsa apply_patch kullan.

Yeni offline deterministik study üret; referans
`/tmp/sloplab-e1e-review-hoxabV/run`. Deterministik yola ledger eklenmesi bu fazda
istenmiyor: aynı 482 dosya kümesi, records/analysis/input identity ham eşitliği
beklenir. Manifest zamanları değişebilir; execution-recipe metadata'sındaki
meşru code/ortam farklarını ayrı göster, semantic hash farkı beklenmez. Pilot
failure çıktıları bilinçli protokol değişimidir; eski failure bayt eşitliği aranmaz.

Teslim `docs/reviews/issue-05/E2a/`: README, outcome-schema.md, commands.jsonl,
kalıcı stdout/stderr/gerçek exit, başlangıç/bitiş hash'leri, E2a diff'i ve yeni
dosya listesi, comparisons.md, run hash envanteri. Kayıt almadan işe başlama;
eksik başlangıcı sonradan uydurma. Önceki dirty/untracked işler kullanıcıya aittir.
Eski arşiv, config/lock/korpus değişikliği, canlı ağ, commit/push yok.

Bitince dur. E2a tamamlandı/kısmi ve E2b/E3'e kalanları açıkça yaz; E2'yi bütünüyle
kapanmış veya canlı pilotu başlatılabilir ilan etme.
