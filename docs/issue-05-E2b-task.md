# E2b — Fiziksel istek bütçesi, retry/deadline ve tekrar kapsamı

Durum: Worker teslimi incelendi; revizyon gerekli. Karar:
[E2b inceleme kaydı](reviews/issue-05/E2b-acceptance.md). Revizyon:
[E2b-r1 görevi](issue-05-E2b-r1-task.md).
Önkoşul: `reviews/issue-05/E2a-acceptance.md`.
Ortak kurallar: [worker teslim protokolü](issue-05-worker-delivery-protocol.md).

## Tek paket hedefi

Her fiziksel LLM dispatch'ini tek bir bütçe sahibinden geçir; retry, pacing ve
`Retry-After` beklemelerini toplam deadline içinde yönet; tekrar kapsamını planlanan
birlik üzerinden doğrula. E2a outcome/karar ayrımı korunur.

## Kapsam ve sözleşme

Önce `adapter.py`, `failures.py`, `pilot.py`, LLM config/runner ve script
tüketicilerini incele. Sayaç ve bütçe sahiplerini envanterle. Public client'a
doğrudan giriş dahil her fiziksel gönderim öncesi atomik olmayan tek-thread
rezervasyon sınırı olsun; bir istek cap'i aşamaz. Adapter attempt ile physical
dispatch aynı isimle sunulmaz.

Parse gibi terminal yerel hatalar retry edilmez. Retry edilebilir transport,
timeout ve provider/rate-limit durumları açık sınıflanır. Request timeout, bütün
işin monotonic deadline'ı, minimum dispatch aralığı ve `Retry-After` ayrı
sözleşmelerdir. Bekleme deadline'a sığmıyorsa uyumadan terminal typed outcome
üretilir. Sahte saat ve transport kullan; gerçek sleep/ağ test koşulu olmasın.

Planlanan tekrar birliği selection identity + evaluator + repeat ile belirlenir.
Başarılı, failed ve not_run outcome anahtarları bununla bire bir uzlaşır. Eksik,
duplicate veya yabancı outcome kapsam hatasıdır. Stability yalnız her seçili vaka
için planlanan tekrarların tamamı başarı olduğunda hesaplanır; coverage sayıları
ve eksiklik nedeni sonuçta görünür.

E3 bundle atomikliği/reader migration'ı, E4 metrik formülleri ve yeni sağlayıcı
entegrasyonu kapsam dışıdır.

## Kabul

1. Retry dahil fiziksel dispatch sayısı cap'i aşmaz; cap 0 ve retry ortasında tükenme testlidir.
2. Terminal parse/config hatası retry edilmez; retry edilebilir türler tanımlı politika izler.
3. Timeout, deadline, pacing ve `Retry-After` sahte saatle bağımsız test edilir.
4. Deadline'a sığmayan bekleme kontrollü failure/not_run üretir; test asılmaz.
5. Ledger ile planned/dispatched/physical/scored sayaçları uzlaşır.
6. Duplicate/eksik repeat kapsamı stability üretmez; tam başarı eski değeri korur.
7. Script ve doğrudan pilot aynı yürütme/muhasebe yolunu kullanır.
8. Sıfır canlı istekle hedefli ve tam offline paket geçer.

Teslim ayrıca `budget-retry-contract.md` ve sayaç denklemlerini içermelidir. E2b
kapanışında E2'nin ne ölçüde kapandığını, E3/E4'e kalanları açıkça yaz.
