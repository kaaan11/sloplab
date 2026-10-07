# İkinci insan değerlendirmesi kontrolü — 3 Ekim 2026

[Hazırlanan paketin](coverage-recovery-2026-10-03.md) Türkçe sürümündeki
`judgment-sheet.json` dolduruldu. Kullanıcı ikinci değerlendiricinin arkadaşı
olduğunu belirtti. Bu kayıt dosya doğrulamasını, betimsel karşılaştırmayı ve
gerekçe incelemesini ayrı sonuçlar olarak raporlar. Ham yanıtlar, isim ve özel
senaryo metinleri erişim kontrollü dizinde kalır.

## Doğrulama sonucu

| İddia | Sonuç | Kanıt ve sınır |
|---|---|---|
| Form eksiksiz ve değerler geçerli | Doğrulandı | 9 kart, 18 iddia durumu, 18 çift; tarih, alanlar, kimlikler, enum değerleri ve gerekçelerin doluluğu doğrulandı. |
| İncelenen girdiler hazırlanan paketle aynı | Doğrulandı | Senaryo ve yönerge hash'leri aynı; yalnızca yanıt formu değişti. Kartlar ilk insanın girdileriyle, çiftler kamuya açık kaynaklarıyla ayrıca eşleşti. |
| Değerlendirici farklı kimlikle kayıtlı | Doğrulandı | İsim/takma ad ilk insanınkinden farklı. Bu kontrolün kapsamı kayıtlı kimliktir. |
| Önceki yanıtlardan etkilenmeden farklı insan doldurdu | Belirsiz | Farklı insan kullanıcı tarafından beyan edildi. Paket önceki oyları içermiyordu; dosya kontrolleri doldurma sırasında ne görüldüğünü veya bağımsız yazarlığı kanıtlayamaz. |
| İlk p10 gerekçesi: A metni imzalama adımını atlıyor | Çürütüldü; düzeltildi | İkinci imzalama adımı A'da mevcut. B'de olup A'da eksik olan üçüncü gönderme/karşılaştırma adımı. İlk teslim özel snapshot'ta korundu. |
| Düzeltilen p10 gerekçesi eksik adımı doğru tanımlıyor | Doğrulandı | Yeni kalite gerekçesi A'daki ikinci yeniden imzalama adımının mevcut, üçüncü gönderme/karşılaştırma adımının eksik olduğunu açıkça belirtiyor. |

**Form kontrolü ve istenen p10 gerekçe düzeltmesi tamamlandı.** Kullanıcının
düzelttiğini bildirdiği formda yalnız p10'un kalite ve eylem gerekçeleri
değişti. Girdiler, kararlar, kart yanıtları ve bütün toplu sayılar aynı kaldı.
Yeni form yeniden doğrulandı, özel snapshot olarak korundu ve toplu JSON'un
kaynak hash'i güncellendi. Kararlar değerlendirici adına değiştirilmedi.
Aşağıdaki sayılar teslim edilen yanıtların betimsel özetidir.

## Kartlar: iki insan arasında uyum

| Alan | Eşleşme |
|---|---:|
| Sonraki eylem | 9/9 |
| Eyleme duyulan güven | 9/9 |
| İddia destek durumu | 16/18 |

İki iddia durumu ayrışması `missing` / `contradictory` ayrımındadır. İlk
insanın dondurulmuş formu veya kapalı yazar anahtarı değiştirilmedi. Bu
ayrışmalar yeni bir ortak hedef karara dönüştürülmedi. Kart girdileri daha
önce proje/model sağlayıcısı tarafından görülmüştür.

## Çiftler: ikinci insan yanıtları

| Kategori | Çift |
|---|---:|
| Yalnız kalite değişti | 9 |
| İkisi de değişmedi | 7 |
| Kalite ve sonraki eylem değişti | 2 |

İki `both` yanıtı yeniden üretim adımı çıkarılan çiftlerde geldi. Bu
cevaplar, tarihsel `decision-preserving` hedeflerini bağımsız olarak
sorgulayan anotasyonlardır. İnsan yanıtını model çoğunluğuyla değiştirmek veya
eski hedefleri otomatik yeniden etiketlemek için kullanılmadı. p10 bunlardan
biridir; düzeltilen gerekçesinde de eylem/kalite kararları korundu.

18 çiftin 17'sinde üç modelin de geçerli oyu var. Bir çiftte Dots oyu eksik;
bu çift tam model çoğunluğu karşılaştırmasına alınmaz.

| Model | Geçerli çift oyu | İnsanla kalite uyumu | İnsanla eylem uyumu |
|---|---:|---:|---:|
| Dots | 17 | 8/17 | 15/17 |
| Liquid | 18 | 6/18 | 16/18 |
| NVIDIA | 18 | 9/18 | 9/18 |

Tam model panellerinde kesin çoğunluğu olan kalite ekseninde **7/13**,
eylem ekseninde **15/17** uyum var. Her iki eksende kesin çoğunluk bulunan
13 çiftin **5'inde** ortak kategori eşleşiyor. Dört kalite ekseninde kesin
çoğunluk yok; bunlar kalite uyumu paydasına katılmaz. Eksik oylar tamamlanmış
panel sayılmaz; belirsiz çoğunluklar kesin karar uyumunun paydasına katılmaz.

Çiftler altı işlem türünden üçer adet olacak şekilde önceki model
belirsizliği/ayrışmasına göre seçildi. Bu seçimin sayıları korpusun tamamına
veya gerçek raporlara genellenemez. Burada yalnız bir insan çiftleri
değerlendirdi; çiftler için insanlar arası uyum ölçülmedi. Kartlarda ise iki
insan arasında bu dokuz örnek üzerindeki uyum ölçüldü.

## Yeniden üretim

`scripts/summarize_independent_review.py` ağ çağrısı yapmadan formu doğrular,
örnek seçimini tekrarlar, ilk insanın dondurulmuş referansını ve kaynak
metinleri kontrol eder. Yalnızca
[toplu JSON](../experiments/results/human-review/independent-2026-10-03/summary.json)
yayımlanır. `validation.complete`, alan/kimlik doğrulamasıdır; gerekçelerin
doğruluğunu hükme bağlamaz.

```bash
uv run python scripts/summarize_independent_review.py \
    --packet-root heldout-private/independent-review/2026-10-03-tr \
    --out /tmp/second-human-summary.json
cmp /tmp/second-human-summary.json experiments/results/human-review/independent-2026-10-03/summary.json
```

Kaynak hash'leri JSON içinde kayıtlıdır. Özel form/girdi dosyaları gerekli
olduğundan form karşılaştırmasını yalnız kamuya açık Git checkout'uyla yeniden
çalıştırmak mümkün değildir. Kamuya açık toplu sayılar ve betimsel aritmetik
ayrıca incelenebilir. ZIP içindeki ilk boş form ve kullanıcı tarafından
doldurulan form korunmuştur.

Ruff lint/format, sıkı mypy, **1230 test** ve 60 kanonik dosya doğrulaması
geçti. Yeni testler özel içerik sızıntısını, eksik model oylarının çoğunluk
paydasına alınmasını, girdi değişimini, aynı değerlendirici kimliğini,
geçersiz/eksik yanıtları ve yinelenen JSON alanlarını denetler. Toplu JSON
aynı baytlarla yeniden üretildi.

Düzeltme kontrolünde 12 ilgili paket/özet testi geçti. Yeni form kaynak
hash'i dışında eski toplu JSON'la tam eşleşti; yeni JSON aynı baytlarla tekrar
üretildi. İlk ve düzeltilen özel teslimlerin ikisi de saklanmıştır.

## Kalan işler

p10 düzeltmesi tamamlandı. Gerekirse iki karttaki iddia durumu ayrışmasının
insanlar arasında ayrıca görüşülmesi sonraki adımdır. Dots'un altı eksik
çift oyu ve kanonik `sqlx-002` HTTP 400 sorunu bu insan değerlendirmesinden
bağımsız olarak sürer. Yeni insan yazımı özel girdiler, kapsamlı yeni tekrar
çalışmaları ve isteğe bağlı genişletmeler [backlog](backlog.md) içindedir.


## 7 Ekim 2026 — Sonraki kullanıcı hükmü

İki kart ayrışması daha sonra kaynak metin ve rubrik karşılaştırmasıyla karara
bağlandı. İki çiftte kalite değişimi kabul edildi; eylem değişimi `uncertain`
olarak bırakıldı. Bu, kullanıcı tarafından kabul edilen ajan destekli bir
hükümdür; yeni kör bağımsız insan değerlendirmesi değildir. Yukarıdaki ilk
anotasyonlar ve 16/18 uyum sayısı değişmedi. Ayrıntı ve kamuya açık toplu kayıt:
[kullanıcı hükmü](user-adjudication-2026-10-07.md).
