# Kapsam tamamlama ve bağımsız inceleme — 3 Ekim 2026

Bu kayıt, [ilk Ekim panelinin](model-panel-followup-2026-10-03.md) ardından
yapılan ek çalışmadır. İlk protokoller, ham istek geçmişleri, kör kullanıcı
formu ve kapalı yazar anahtarı korunmuştur. Yeni istekler eski başarısızlıkların
yerine yazılmamış, ayrı ve çağrıdan önce kayıtlı ek protokollere bağlanmıştır.

## Ek çağrıların sözleşmesi

`scripts/complete_panel_coverage.py`, yalnızca geçerli oyu bulunmayan
kart/model veya batch/model slotlarını seçer. Önceki protokolün ve bütün önceki
kayıtların hash'lerini, aynı model kimliklerini ve aynı istek ayarlarını
sabitler. Slot başına en çok üç yeni çağrı, başarıdan sonra durma ve yalnızca
son ek çalışmayı sürdürme kuralları uygulanır. Geçmiş başarısızlıklar,
fiziksel istek toplamları ve ek protokol/kayıt hash'leri görünür kalır.

```bash
# Ön kontrol; çağrı yapmaz.
uv run python scripts/complete_panel_coverage.py --kind edits --run-id recovery-20261003-02
# --run canlı çağrıyı, --resume son kayıtlı çalışmayı sürdürmeyi açar.
```

## Dokuz özel kart

Eksik iki Qwen oyu ilk yeni denemelerinde geçerli döndü. Artık **27/27 oy**,
**9/9 tam kart**, ilk 36 + önceki ek 6 + bu ek 2 = **44 fiziksel istek** var.
Özel girdiler ve ham yanıtlar Git'e eklenmez; yalnızca
[toplu özet](../experiments/results/model-panel/coverage-recovery-2026-10-03/private-cards/summary.json)
yayımlanır.

| Model | Geçerli oy | İlk insanla eylem uyumu | İddia durumu uyumu | Güven uyumu |
|---|---:|---:|---:|---:|
| Qwen | 9/9 | 9/9 | 17/18 | 9/9 |
| Dots | 9/9 | 9/9 | 15/18 | 8/9 |
| Liquid | 9/9 | 4/9 | 15/18 | 8/9 |

Beş kartta en az bir eylem, dört kartta en az bir iddia durumu ayrışması var.
Bunlar ilk insanın kör yanıtlarıyla betimsel uyumdur; doğruluk veya bağımsız
insanlar arasında güvenilirlik iddiası değildir. İlk insan formunun SHA-256'sı
`ccb0271bf20d5e93960a7473da34d4c18f7c31dffbca4ff564fcda790fcc9a26`
olarak korunmuştur.

## 141 kamuya açık rapor çifti

Üç eksik batch/model slotu için ek üst sınır dokuz çağrıydı. Liquid
`batch-028` ikinci yeni denemede geçerli üç oy verdi. Dots `batch-031` ve
`batch-040` için üçer yeni deneme HTTP 400 verdi. Toplam **sekiz yeni çağrı**,
ilk 159 ile **167 fiziksel istek** ve **417/423 geçerli oy** var.

| Tam çiftlerde betimsel çoğunluk | Çift sayısı |
|---|---:|
| Yalnız kalite değişti | 56 |
| İkisi de değişmedi | 75 |
| Belirsiz | 4 |
| Eksik Dots oyu | 6 |

135 tam çiftin 117'sinde en az bir eksende model ayrışması var. NVIDIA ve
Liquid 141'er, Dots 135 geçerli oy verdi. Eski yazar hedefleri değişmedi.
[Kamuya açık protokol, anotasyonlar ve özet](../experiments/results/model-panel/coverage-recovery-2026-10-03/realized-edits/)
özel dosyalara veya ağ erişimine gerek olmadan yeniden hesaplanabilir:

```bash
uv run python scripts/summarize_realized_edit_panel.py \
    --bundle experiments/results/model-panel/coverage-recovery-2026-10-03/realized-edits \
    --out /tmp/recovered-edits
```

## Kanonik sqlx-002 teşhisi ve ayrı model çalışması

`scripts/diagnose_llm_case.py` özgün kamuya açık rapor, `triage-v1` promptu ve
sıkı yanıt şeması ile tek fiziksel çağrı sınırı uygular; protokol çağrıdan önce
yazılır. Dots'taki tek yeni teşhis yine HTTP 400 verdi. Ham hata gövdesi yalnız
genel "bad request" açıklaması içerdi; kök nedeni saptanamadı. Bu teşhis,
Eylül'deki altı başarısız gözlemin yerine yazılmadı.

NVIDIA'nın ücretsiz varyantında aynı girdi/şema için tek teşhis başarılıydı.
Ardından **ayrı kayıtlı üç tekrarlı NVIDIA çalışması** üç geçerli `accept`
yanıtı verdi, hiç hata vermedi ve üç fiziksel çağrı kullandı.
[Doğrulanmış bundle](../experiments/results/llm-pilot/2026-10-03/sqlx-nvidia-recovery/)
prompt ve şema hash'lerini korur; modeli farklıdır. Orijinal Dots çalışmasının
kapsamı **59/60** olarak kalır. Modeller birleştirilerek Dots için 60/60
sonuç veya genel doğruluk iddia edilmez.

Bu takipte 2 kart + 8 çift + 2 teşhis + 3 NVIDIA tekrarı = **15 canlı model
çağrısı** yapıldı. Kalan altı çift oyu ve özgün kanonik Dots gözlemi için
sağlayıcı hatası hâlâ engeldir. Bu HTTP 400'lerden günlük istek kotasının
tükendiği sonucu çıkarılamaz; nedeni kanıtlanmış değildir.

## İkinci insan: arkadaş değerlendirmesi

Kullanıcı ikinci değerlendiricinin arkadaşı olacağını belirtti. Paket
`scripts/prepare_independent_review.py` ile hazırlanır: dokuz kart, altı
işlem türünden üçer olmak üzere 18 çift, Türkçe yönerge, rubrik ve boş JSON
formu. Çift seçiminde önce belirsizlik, sonra model ayrışması ve deterministik
hash sırası kullanılır; bir yaygınlık örneklemi değildir. Model oyları ve ilk
insan yanıtları görünür pakete kopyalanmaz. Kimlik eşlemesi ve seçim kaydı
ayrı `admin-protocol.json` dosyasında tutulur, paylaşılabilir ZIP'e girmez.

Hazırlanan özel paket:
`heldout-private/independent-review/2026-10-03-tr/reviewer-packet.zip`.
ZIP SHA-256:
`aab9a3eb61067be2735ba5a421de1cc6c028596d987cfdd414fe796d9eafb6c6`.
Arkadaşın yalnızca paketi inceleyip bütün alanları doldurduğu
`judgment-sheet.json` dosyasını geri vermesi gerekir. İsim yerine farklı bir
takma ad kullanılabilir. İnsan yanıtı bekleniyor; sonuç üretilmedi veya
insanlar arası uyum hesaplanmadı. Paket daha önce proje/sağlayıcı tarafından
görülmüş girdilerden oluşur; yeni bir görülmemiş küme değildir.

## Tekrar analizi ve kalan iş

[Çevrimdışı varyans CLI'si](variance-analysis.md), doğrulanmış çalışmaları
birleştirir, model koşullarını ayırır, başarısızlıkları görünür tutar ve
mantıksal rapor kümesi bootstrap aralıkları verir. Eylül'ün dokuz bundle'ı
için yeniden üretilebilir JSON da yayımlanmıştır. Birden fazla temel tohum
okunabilir; bu eski çalışmalarda sağlayıcı çözümleme tohumu kontrol edildiği
iddia edilmez.

İkinci insan formu, Dots sağlayıcı sorunu, yeni insan yazımı özel girdiler
ve önceden kayıtlı geniş tekrar/mutasyon deneyleri kalan doğrulama işleridir.
İsteğe bağlı ürün genişletmeleri [backlog](backlog.md) içinde durur. Bu kayıt
bu işlerin tamamının bittiği anlamına gelmez.

## Doğrulama

Bu dalda kilitli bağımlılık senkronizasyonu, Ruff lint/format, sıkı mypy,
**1220 test**, 60 kanonik dosya doğrulaması ve BYOE/tekrarlı çevrimdışı HTML
kontrolü geçti. İlk ve yeni kamuya açık panel bundle'ları aynı baytlarla
yeniden üretildi; NVIDIA bundle hash'leri doğrulandı. Eylül varyans JSON'u
aynı baytlarla üretildi. Özel girdiler, dolu insan formu, yazar anahtarı ve
ham sağlayıcı yanıtları commit kapsamı dışında tutuldu.
