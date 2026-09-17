# Issue 05 — Bütünleşik kapanış doğrulaması

Durum: Kabul edildi. Kabul kaydı:
[bütünleşik kapanış kabulü](reviews/issue-05/integration-acceptance.md). E0–E5
kabul edildi. Ortak kurallar:
[worker teslim protokolü](issue-05-worker-delivery-protocol.md).

## Hedef

Yeni özellik eklemeden kabul edilmiş paketlerin birlikte aynı sözleşmeleri
koruduğunu doğrula. Tek referans ortamda temiz, tamamen offline iki uçtan uca run
üret; bundle, provenance, outcome, coverage, analiz ve E5 üretim sürümü bağlarını
bağımsız denetle.

İki run farklı ve yeni geçici köklerde, aynı sabit config ve aynı mevcut çalışma
ağacı snapshot'ından üretilmelidir. Karşılaştırma politikası koşudan önce yazılsın:
izin verilen değişken metadata alanları açıkça listelensin; diğer her fark dosya,
JSON yolu ve gerekçesiyle raporlansın. `/tmp` yolları kanıtın kendisi sayılmaz;
yeniden üretim komutları ve hash envanterleri teslim dizininde saklansın.

## Kabul

- Aynı girdili iki run'da politika dışı deterministik fark yoktur.
- Hash zincirleri kaynak→selection→recipe→records/outcomes→analysis boyunca çözülür.
- Sayaçlar ledger ve records ile; materialization defteri suite/index ile uzlaşır.
- Failed/not_run hiçbir karar metriğine girmez; eksik coverage görünürdür.
- Strict okuyucu kesik/karışmış/stale negatif fixture'ları reddeder.
- Tarihsel artefakt envanteri değişmez; yeni üretim/analiz sürümleri ayrıdır.
- Tam offline test, lint/format/type ve `git diff --check` geçer.
- Canlı pilot hazır olma hükmü yalnız E0–E5 kapıları ve açık bilimsel kararlar
  birlikte değerlendirilerek verilir; maliyet/sağlayıcı davranışı uydurulmaz.

Bir kabul sözleşmesi bozulursa sonucu gizlemek için kodu veya fixture'ı sessizce
değiştirme. Karşıörneği, etkilenen paket bağını ve önerilen en küçük revizyonu
teslimde ayrı bir bloklayıcı bulgu olarak kaydet.

Teslim `README.md`, `integration-matrix.md`, koşu öncesi fark politikası, iki run
hash envanteri ve karşılaştırma çıktısı, komut/exit-code kayıtları, açık bilimsel
kararlar ve koşullu E6 gereksinimi hakkında hüküm içermelidir. Matris her E0–E5
sözleşmesini onu doğrulayan dosya, komut ve gözlenen sonuçla eşlemelidir.

Worker çıktıları, komut kayıtları ve iki run'a ait karşılaştırma kanıtları
`docs/reviews/issue-05/integration/` altında belge olarak korunmalıdır. Ana
inceleyici teslimi bağımsız doğrulayacak; worker'ın kabul beyanı yeterli değildir.
