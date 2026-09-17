# E2b — Ana inceleyici kararı: revizyon gerekli

Tarih: 2026-09-09. **E2b kabul edilmedi; E2b-r1 revizyonu gerekli.**

## Karar

Worker teslimi yapılandırılmış kanıt, 7 yeni test, 132 hedefli test ve 270 testlik
tam paket sunuyor. Parse/config terminal davranışı, retry sınıflandırması, ledger
kapsam denetimi ve fake-clock bekleme testleri faydalı. Worker loglarında hedefli
ve tam testler, ruff/format/mypy, hash doğrulaması ve deterministik study
karşılaştırması exit 0 görünüyor. Ana inceleyici E2b'nin 7 yeni testini yeniden
çalıştırdı; hepsi geçti. `git diff --check` ve teslim hash envanteri temiz.

Buna rağmen fiziksel dispatch muhasebesi ve toplam deadline kabul ölçütleri
sağlanmıyor. Bunlar paketin ana hedefi olduğu için belge düzeltmesiyle kabul
verilemez.

## Bloklayıcı bulgular

### 1. `requests` fiziksel dispatch sayacı değil

Üretim zinciri `CountingClient(ThrottledClient(HttpLLMClient))` biçiminde.
`CountingClient.complete()` önce rezervasyonu artırıyor, sonra `ThrottledClient`
pacing veya `Retry-After` beklemesini deniyor. Bekleme deadline'a sığmadığında
alttaki transport hiç çağrılmadığı halde `requests` artmış oluyor.

Ana inceleyici karşıörneği:

```text
DeadlineExceeded
reported_requests 2 actual_transport_calls 1 sleeps []
```

Bu nedenle manifestodaki `counters.requests` “physical dispatch” diye sunulamaz.
Rezervasyon, attempt ve gerçekten başlayan transport dispatch ayrı anlamlardır;
cap sahipliği korunurken sayaçların bu ayrımı taşıması gerekir.

### 2. Teslimdeki sayaç denklemi retry durumunda ters

`budget-retry-contract.md`, `physical <= dispatched` diyor. Buradaki dispatched
`successful + failed` evaluation sayısıdır. Bir evaluation retry yaptığında birden
fazla fiziksel dispatch oluşur. Ana inceleyici tek evaluation'ın iki timeout sonrası
başarıya ulaştığı karşıörneği çalıştırdı:

```text
evaluations_attempted 1 reported_requests 3 actual_transport_calls 3 successful 1
```

Dolayısıyla genel ilişki `physical <= dispatched` değildir. Doğru denklemler retry,
bütçe/deadline öncesi reddedilen rezervasyon ve gerçek transport başlangıcını ayrı
saymalıdır. Testte yalnız üç terminal failure seçilmesi bu hatayı görünmez bırakmış.

### 3. Toplam deadline HTTP isteğini sınırlandırmıyor

`CountingClient.set_deadline()` yalnız destekleyen iç wrapper'lara çağrı iletiyor.
`ThrottledClient` deadline'ı yalnız pacing/`Retry-After` beklemelerinde kullanıyor;
`HttpLLMClient` bir `set_deadline` sözleşmesi taşımıyor ve `urlopen` için her zaman
sabit `request_timeout_s` veriyor. Kalan toplam süre request timeout'tan kısa olsa
bile yeni HTTP dispatch daha uzun timeout ile başlatılabilir. Bu, bütün koşunun
monotonic deadline'ı iddiasını sağlamaz.

### 4. Karşılaştırma provenance'ı yanlış adlandırılmış ve önceki temp yolu yeniden kullanılmış

E2b teslimi yeni run kökü oluşturduğunu kaydetmesine rağmen sonraki komutlarda
`E2A_RUN_ROOT` ve `/tmp/sloplab-e2a-u0PKCr/run` kullanmış. README ve comparisons
dosyaları da bunu “E2b koduyla yeni koşu” diye sunuyor. Deterministik veri
karşılaştırması exit 0 olsa da E2a referans yolu üzerine yeniden yazılmış ve E2b
run kimliği doğru kaydedilmemiş. `/tmp` arşiv değildir, fakat faz karşılaştırması
benzersiz yeni kök ve doğru provenance ile tekrar üretilmelidir.

## Korunacak işler

Worker'ın failure sınıflandırması, terminal parse/budget/deadline politikası,
coverage checker'ı ve mevcut testleri korunabilir. Ham worker README, diff, log ve
hash dosyaları `docs/reviews/issue-05/E2b/` altında değiştirilmeden teslim kanıtı
olarak kalmalıdır.

Sıradaki çalışma [E2b-r1 görev dosyasıdır](../../issue-05-E2b-r1-task.md). E2
kapanmadı; E3 uygulamasına ve canlı pilota geçiş için kabul verilmedi.
