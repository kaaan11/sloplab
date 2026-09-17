# E1c — Gönderilen prompt ile kaydedilen kimliği bağlama

Durum: Hazır, henüz uygulanmadı. Yürütücü: Luna. Kök: `/home/kaan/sloplab`.
Önkoşul: [E1b kabulü](reviews/issue-05/E1b-acceptance.md).

## Amaç

Pilot şu anda config.prompt_file dosyasını çalışma sonunda hash'liyor; adapter
ise başka bir PROMPT_TEMPLATE sabitini gönderiyor. Bu pakette pilotun kullandığı
şablon ile kaydettiği kimlik aynı, çalışma başında çözülmüş girdiden gelmeli.
Bu, opt-in LLM protokol düzeltmesidir; canlı API çalıştırılmayacak.

## Kapsam ve okuma

Geçerli AGENTS.md yönergelerini oku. Sonra yalnız adapter.py, experiments/pilot.py,
experiments/config.py içindeki LLMPilotConfig, scripts/llm_bench.py,
experiments/prompts/triage-v1.md, ilgili adapter/pilot/script testleri ve E1b
snapshot testi yeterlidir. Gerekli modelleri doğrudan bağımlılık olarak incele.
Bilimsel raporları veya diğer projeleri tarama; alt ajan başlatma.

İzinli değişiklikler: adapter ve pilot prompt bağlantısı, gerekirse küçük bir
prompt yardımcı modülü, dar script bağlantısı, ilgili testler ve sözleşme belgesi.
Kabul edilmiş E1a/E1b değişikliklerini koru; başlangıç kimliklerini araçla üret.
Hash'leri elle yazma/kopyalayıp yeniden birleştirme. Kullanıcı dosyalarını koru.

## Kesin sözleşme

1. Pilot için prompt kaynağı `repo_root / config.prompt_file` olsun; mutlak yolun
   mevcut Path davranışını koru. Dosya yalnız bir kez, ilk evaluator/transport
   çağrısından ve çıktı dizini oluşturulmasından önce okunup UTF-8 çözülür.
2. Okunan aynı immutable metin pilotun tüm vaka/tekrar/retry çağrılarında kullanılır.
   Çalışma sırasında dosyanın değişmesi veya silinmesi gönderilen metni veya
   manifesto kimliğini değiştiremez. Sonunda dosyayı tekrar hash'leme.
3. Dosya tam olarak bir `{report_text}` yer tutucusu içermeli. Sıfır veya birden
   fazla yer tutucuyu, okunamayan dosyayı ve geçersiz UTF-8'i dispatch öncesi
   açıklayıcı config hatasıyla reddet. Çıktı dosyaları bu hatada oluşmamalı.
4. Renderer yalnız bu tanımlı yer tutucuyu işler. JSON süslü parantezleri ve
   raporun içindeki `{report_text}`, `{}`, Unicode gibi içerikler ikinci kez
   yorumlanmaz. Prompt dosyasını doğrudan `.format()` ile render etme.
5. Mevcut bağımsız `LlmEvaluator(client=..., enabled=True)` kurucusu çalışmaya
   devam etmeli; varsayılan prompt'un gönderilen metni bayt düzeyinde korunmalı.
   Mevcut sabitte JSON için çift süslü parantez bulunduğunu gözet. Genel
   parantez replace'iyle dosya prompt'unu bozmadan legacy render uyumunu sağla.
6. Pilot, config prompt'unu evaluator'a açık bir API ile bağlamalı. Küçük bir
   `with_prompt`/kopyalama yöntemi veya eşdeğeri kullanılabilir; çağıranın evaluator
   nesnesini gizlice kalıcı olarak değiştirme. Aynı CountingClient nesnesi ve
   retry ayarları korunmalı; sayaçları sıfırlayan yeni client oluşturma.
7. Manifestodaki `prompt_hash` alanını koru, anlamını açıkça tanımla: pilot için
   okunan orijinal UTF-8 template baytlarının SHA-256'sı. Satır sonlarını sessizce
   normalize etme. `prompt_renderer_version` gibi açık render sürümünü kaydet.
8. Her normalize evaluation sonucunun metadata'sına gönderilen **prompt metninin**
   UTF-8 SHA-256'sını `rendered_prompt_hash` olarak bağla. Bu HTTP gövdesi/model/
   sampling ayarlarını içeren tam request hash'i değildir; öyle adlandırma.
   Başarılı ve mevcut failed-result yolunda aynı gözleme ait hash korunmalı.
   Retry'lar aynı render edilmiş prompt'u kullanmalı.
9. Yeni içerik hash'lerini deterministik evaluator kayıtlarına ekleme. Ham LLM
   cevabı, credential veya prompt'un tamamını yeni provenance alanlarına yazma.

Config prompt'u pilot için yetkilidir; sonradan dosya okunup yalnız kimlik
doğrulaması yapılması yeterli değildir. Script ve doğrudan pilot API aynı
davranışı sağlamalı. Hata sınırını geniş `except Exception` ile kapatma.

## Kapsam dışında

Outcome şeması, failed→review sorunu, severity bug'ı, JSON yanıt parser politikası,
bütçe/retry algoritması, rate limiting, sampling ayarları, canonical/derived kayıt
kusurları, kimlik gizleme genişletmesi ve metrik düzeltmesi bu pakette yapılmaz.
Prompt dosyasındaki bilimsel rubric yeniden yazılmaz. Pilotta gerçek dosya
prompt'una geçişin eski hard-coded prompt'tan farklı olduğunu açıkça belgele;
bu değişimi sadece metadata düzeltmesi diye sunma. Canlı pilot başlatma.

## Kabul testleri

- Fake transport'a kaydedilen metin config dosyasının talimatlarını içerir;
  manifest prompt_hash'i tam başlangıç baytlarından bağımsız hesapla.
- İlk completion sırasında template dosyasını değiştir/sil; sonraki vaka,
  tekrar ve retry aynı ilk şablonu kullanır, manifesto hash'i ilk sürümde kalır.
- Farklı template ile yeni pilot farklı metin/hash üretir. Aynı template farklı
  raporlarda aynı template hash'i, farklı rendered_prompt_hash üretir.
- Fake transport'un gerçekten aldığı prompt'un UTF-8 hash'i metadata ile aynıdır;
  failure ve retry yolunu da kapsa. Fake response ve sahte hata kullan.
- JSON parantezleri, LF/CRLF, Türkçe/Unicode ve rapor içindeki yer tutucular
  korunur; geçersiz template'lerde dispatch sayısı sıfırdır ve mevcut geçici
  çıktı dizinindeki sentinel içeriği/dosya kümesi değişmez.
- Standalone adapter default prompt'u önceki render sonucu ile eşittir.
  Pilot bağlamasından sonra çağıranın evaluator default/custom ayarı değişmez.
- Mevcut fake adapter/pilot/script testleri ve E1b snapshot testleri geçer.
  Mevcut testleri yalnız açıkça değişen pilot prompt beklentileri için güncelle;
  budget/snapshot kontrollerini gevşetme.

Hedefli testleri ve değişen dosyalarda lint/format/type kontrollerini çalıştır.
Yeni bir offline deterministik study üretip E0 veya E1b referansıyla karşılaştır:
tam dosya kümesi aynı, 479 veri/index dosyası ham eşit, manifestoda yalnız
açıklanmış zaman farkları. Eski arşiv veya karşılaştırma allowlist'ini değiştirme.

## Teslim

`docs/reviews/issue-05/E1c/` kullan; doluysa yeni numaralı kardeş seç.
README, prompt sözleşmesi, gerçek komut/exit/log taşıyan commands.jsonl,
kalıcı test/stdout/stderr günlükleri, karşılaştırma özeti ve output hash envanteri
teslim et. Büyük run dizini yeni bir `/tmp/sloplab-e1c-XXXXXX/` altında olabilir.

Başlangıç/bitiş kaynak hash'lerini programatik üret ve her satırın 64 hex karakter
olduğunu doğrula. Geçmişte kaydedilmemiş hash'i bugünden başlangıç diye yazma.
E1a/E1b'den ayrı E1c diff'ini ve yeni test dosyalarını listele. Kaynak düzenlemesi
için mevcutsa apply_patch kullan. Commit/push, canlı istek veya network kurulum yok.

Bitince dur; E1c tamamlandı/kısmi durumunu yaz. E1'in tamamı henüz kapanmaz:
stimulus/hedef/seçim kimlikleri ve tam etkili deney tarifi başka bir pakettir.
