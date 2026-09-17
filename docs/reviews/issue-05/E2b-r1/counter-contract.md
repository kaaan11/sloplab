# E2b-r1 — Sayaç sözleşmesi (counter-contract.md)

Üretim zincir sırası: `LlmEvaluator → ThrottledClient → CountingClient →
transport`. Sıra sözleşmenin parçasıdır: pacing ve `Retry-After` beklemeleri
(ve deadline redleri) rezervasyonun *üstünde*, rezervasyon fiziksel transport
başlangıcının *hemen önünde* gerçekleşir.

## Birimler

- `evaluations_attempted = successful + failed` (değerlendirme; `not_run` hariç).
- `adapter_attempts`: evaluator çağrısındaki mantıksal deneme sayısı
  (1 + tüketilen retry; gözlem başına, outcome satırında).
- `physical_dispatches`: gerçekten başlayan transport çağrısı sayısı
  (`CountingClient` sayacı; rezervasyonla bire bir).
- `reservations`: ayrı sayaç YOKTUR. Rezervasyon artışı ile transport
  başlangıcı arasında ret yolu bulunmadığı için iptal/consume semantiğine
  gerek yoktur; tek sayaç her ikisini de tutar.
- `errors` / `timeouts`: rezervasyon sonrası transport hataları (timeout ayrıca
  sayılır). Ret öncesi reddedilen rezervasyon (bütçe/deadline) bunları artırmaz.

## Neden bire bir

`CountingClient.complete()`: (1) deadline geçmişse artırmadan
`DeadlineExceeded`; (2) cap doluysa artırmadan `BudgetExhausted`; (3) artırıp
hemen `inner.complete()` çağırır. Arada uyku, bekleme veya ret yoktur.
`ThrottledClient` pacing/`Retry-After` redleri bu kapının üstünde olur, sayaç
görmez. Sonuç: `physical_dispatches == reservations consumed ==
transport starts` (gerçek saatte deadline'ın iki okuma arasına düşmesi gibi
kaybolacak kadar dar yarış dışında; testlerde sahte saatle tam).

## Exact denklemler (yol başına)

- Success-after-retry (k timeout + başarı, `max_retries >= k`):
  `evaluations=1`, `adapter_attempts=k+1`, `physical=k+1`.
  Retry `physical > evaluations` yapabilir (E2b'nin `physical <= dispatched`
  iddiası bu yüzden genelde yanlıştır).
- Permanent failure (hep timeout, retry tükenir, cap'e değmez):
  `evaluations=1`, `attempts=max_retries+1`, `physical=max_retries+1`,
  outcome `failed(timeout)`.
- Cap-in-retry (cap=C, hep timeout): ilk C deneme reserve+dispatch eder;
  C+1. deneme artırmadan `BudgetExhausted` → outcome `failed(budget)`,
  `adapter_attempts=C+1`, `physical=C`, `timeouts=C`, `errors=C`
  (reddedilen rezervasyon error/timeout saymaz).
- Pacing-deadline reddi: başlamış plan `failed(deadline)`,
  `adapter_attempts=1`, `physical` değişmez, uyku yok; başlamamış planlar
  `not_run(deadline_exceeded)`. İnceleyici karşıörneği:
  `physical_dispatches == actual_transport_calls == 1`.
- Pre-dispatch deadline (`CountingClient` kapısı): muhasebe pacing-reddiyle
  aynıdır (artış yok, transport yok); pilot ayrıca vaka dispatch'inden önce
  deadline'a bakar ve geç planları `not_run(deadline_exceeded)` yapar.
- Post-dispatch `Retry-After` reddi: 429 gerçekten geldiği için o dispatch
  physical sayılır; bekleme sığmazsa failure `deadline` olur (429 değil).

## Zaman sözleşmeleri (dördü ayrıdır; E2b'den devralındı, biri sıkılaştı)

- `request_timeout_s`: tek HTTP isteği üst sınırı (E2b-r1'de deadline
  kısıtıyla: `urlopen` timeout = `min(request_timeout_s, remaining)`).
- `deadline_s` (opsiyonel): tüm koşunun monotonic bitiş anı. E2b-r1'de
  `HttpLLMClient` katmanına ulaşır (`set_deadline` zinciri); süre bitmişse
  HTTP çağrısı başlamadan terminal deadline sonucu oluşur.
- `min_interval_ms`: dispatch başlangıçları arası pacing. Ölçüt yalnızca
  gerçek dispatch'lerde ilerler; ret öncesi redler tabanı bozmaz.
  `sleep_cap_s` YALNIZCA pacing uykularını sınırlar (test hook).
- `Retry-After`: sağlayıcı bekleme talebi; her zaman tamamı uygulanır,
  cap ile sessizce kısaltılmaz. Üretim yolunda cap yoktur (`llm_bench.py`
  artık `sleep_cap_s` geçmez).

## Şema notu (bilinçli fark)

Manifesto ve `PilotRunResult.counters` anahtarı `requests` →
`physical_dispatches` olarak yeniden adlandırıldı (birim aynı, anlam artık
exact). E2b kanıtları değiştirilmedi.
