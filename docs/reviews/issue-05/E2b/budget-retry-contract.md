# E2b — Bütçe/retry sözleşmesi (budget-retry-contract.md)

## Sahiplik

- Fiziksel gönderimlerin tek sahibi `CountingClient`'tır:
  `_reserve_or_raise()` her `complete()` çağrısında cap'i dener; aşım
  `BudgetExhausted` yükseltir ve sayaç artmaz. Doğrudan client girişi dahil
  hiçbir yol bu kapıyı atlayamaz. Artışın kendisi rezervasyondur (tek-thread;
  thread-ötesi atomiklik iddia edilmez).
- Pilotun dispatch-öncesi `requests >= effective_cap` kontrolü planlama
  amaçlıdır (`not_run` satırları üretir), ikinci sahip değildir: gönderimi
  durduran kapı `CountingClient`'tır.

## Sayaç denklemleri

- `planned = successful + failed + not_run` (defterde her plan tek satır).
- `dispatched = evaluations_attempted = successful + failed` (`not_run` hariç;
  records satır sayısına eşitlenmez).
- `physical = counters.requests` (kapıdan geçen gönderimler).
- `scored = successful`.
- İlişki: `physical <= dispatched`; bütçe kapısına takılan deneme gönderilmediği
  için eşitlik yalnızca kapı teması yoksa korunur. `adapter_attempts` (mantıksal,
  gözlem başına) ile `requests` (fiziksel, sayaç) farklı isimlerdedir ve
  birbirinin yerine kullanılmaz.

## Retry politikası

| Tür | Davranış | failure türü |
| --- | --- | --- |
| parse (`_ParseFailure`) | terminal, retry yok | `parse` + parser sabit kodu |
| config (`PromptTemplateError` vb.) | dispatch öncesi ret | failure değil, hata yükselir |
| budget (`BudgetExhausted`) | terminal, retry yok | `budget` / `budget.exhausted` |
| deadline (`DeadlineExceeded`) | terminal, retry yok | `deadline` / `deadline.exceeded` |
| timeout (`TimeoutError`) | retry (`max_retries`) | `timeout` / `transport.timeout` |
| transport (diğer) | retry (`max_retries`) | `transport` / `transport.error` |
| rate-limit (`code == 429`) | retry (`max_retries`) | `rate-limit` / `rate_limited` |

Detaylar sabit koddur; exception metni (credential/URL/ham cevap taşıyabilir)
kopyalanmaz. Beklenmeyen program hataları ve config hataları failure'a
çevrilmez, aynen yükselir.

## Zaman sözleşmeleri (dördü ayrıdır)

- `request_timeout_s`: tek HTTP isteği üst sınırı (transport katmanı).
- `deadline_s` (opsiyonel): tüm koşunun monotonic bitiş anı (`start + deadline_s`;
  `None` = kapalı). Dolmadan biten koşuda etkisi yoktur.
- `min_interval_ms`: dispatch başlangıçları arası pacing (uyulması zorunlu
  bekleme; deadline'a sığmazsa uyumadan `DeadlineExceeded`).
- `Retry-After`: sağlayıcı bekleme talebi (deadline'a sığmazsa uyumadan
  `DeadlineExceeded`).
- Pilot ayrıca her vaka dispatch'inden önce deadline kapısına bakar; geç kalmış
  planlar `not_run(reason=deadline_exceeded)` olur. Başlamış denemenin beklemesi
  sığmazsa `failed(error_kind=deadline)` olur.

## Kapsam birliği

Planlanan küme = seçili `case_id` × evaluator × `repeat`. Defter anahtarları
bununla bire bir uzlaşır (`check_outcome_coverage`): eksik/duplicate/yabancı/
bozuk satır kapsam hatasıdır; pilot kendi defterini doğrular.
Stability yalnızca her seçili vaka × planlanan repeat tam başarılıysa hesaplanır;
manifestoda `coverage {expected, successful, complete}` ve eksiklik nedeni
(`stability_omitted_reason`) görünür. Tam-başarı değerleri değişmedi.
