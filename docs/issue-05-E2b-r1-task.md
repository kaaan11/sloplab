# E2b-r1 — Dispatch muhasebesi ve gerçek toplam deadline revizyonu

Durum: Worker teslimi incelendi; ikinci revizyon gerekli. Karar:
[E2b-r1 inceleme kaydı](reviews/issue-05/E2b-r1-acceptance.md). Revizyon:
[E2b-r2 görevi](issue-05-E2b-r2-task.md). Kök: `/home/kaan/sloplab`.
Yürütücü: worker model.
Önkoşul:
[E2b inceleme kararı](reviews/issue-05/E2b-acceptance.md).
Ortak kurallar: [worker teslim protokolü](issue-05-worker-delivery-protocol.md).

## Tek hedef

E2b'nin korunabilir retry/coverage uygulamasını sürdür; rezervasyon, evaluator
attempt ve gerçekten başlayan fiziksel transport dispatch sayaçlarını doğru ayır;
toplam deadline'ı üretim HTTP isteğinin timeout'una kadar uygula. E2b'deki dört
bloklayıcı bulguyu kapat.

## Zorunlu sözleşme

- Hard cap'in tek sahibi her fiziksel transport başlangıcından hemen önce
  rezervasyon yapmalı. Pacing/`Retry-After` nedeniyle deadline reddi transport
  başlamadan gerçekleşirse fiziksel dispatch sayacı artmamalı. Ayrı bir reservation
  sayacı tutuluyorsa adı ve iptal/consume davranışı açık olmalı.
- `evaluations_attempted = successful + failed`; `adapter_attempts` evaluator
  çağrısındaki mantıksal denemelerdir; `physical_dispatches` gerçekten başlayan
  transport çağrılarıdır. Retry nedeniyle physical dispatch evaluation sayısından
  büyük olabilir. Bütçe/deadline kapısında başlamayan deneme physical değildir.
- Sayaç denklemlerini eşitsizlik tahminiyle değil ledger ve attempt olaylarıyla
  tanımla. Success-after-retry, permanent failure, cap-in-retry, pacing deadline
  reddi ve pre-dispatch deadline yollarının her birinde exact değer test et.
- Monotonic run deadline üretim `HttpLLMClient` katmanına ulaşmalı. Her HTTP
  dispatch öncesi kalan süre hesaplanmalı; `urlopen` timeout değeri
  `min(request_timeout_s, remaining_run_time)` olmalı. Kalan süre pozitif değilse
  HTTP çağrısı başlamadan terminal deadline sonucu oluşmalı.
- Pacing ve `Retry-After` deadline'a sığmıyorsa uyuma ve dispatch etme. Test hook'u
  olan sleep cap üretimde sağlayıcının `Retry-After` süresini sessizce kısaltmamalı;
  production davranışını açık test et.
- Exception metni veri minimizasyonu, terminal parse/config davranışı, label
  sınırı ve outcome karar ayrımı korunmalı.

## Kabul testleri

1. Reviewer karşıörneği: ilk çağrı gönderilir, ikinci pacing beklemesi deadline'a
   sığmaz; `physical_dispatches == actual_transport_calls == 1`.
2. Tek evaluation iki timeout sonrası başarı: evaluations=1, adapter attempts=3,
   physical dispatches=3; manifest ve result aynı değerleri verir.
3. Retry ortasında cap: cap aşılmaz; reddedilen rezervasyon physical dispatch
   değildir; outcome budget failure ve sayaçlar exact uzlaşır.
4. HTTP request başlarken kalan deadline request timeout'tan küçükse fake
   `urlopen` kalan süreyi timeout olarak görür; süre bitmişse hiç çağrılmaz.
5. Uzun `Retry-After`, deadline varsa hızlı terminal; deadline yoksa production
   yolu değeri sessizce kısaltmaz. Sahte saat kullanılır, gerçek sleep yoktur.
6. Mevcut E2a/E2b hedefli testler ve tam offline paket geçer.

## Teslim

Yeni kanıt dizini `docs/reviews/issue-05/E2b-r1/` olmalıdır. Eski E2b kanıtlarını
değiştirme. `counter-contract.md` içinde her sayacın birimi ve exact denklemleri
bulunsun. Benzersiz `/tmp/sloplab-e2b-r1-XXXXXX` kökünde yeni deterministic study
çalıştır; komut ve belge değişkenlerinde E2b-r1 adını kullan, E2a yolunu yeniden
kullanma. E1e/E2a referansına göre ham/semantik farkları kaydet.

E2b-r1 tamamlandığında E2'nin kabul edildiğini yalnız ana inceleyicinin yeni kabul
kaydı belirler. E3 veya canlı pilot hazır ilan edilmez.
