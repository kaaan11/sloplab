# E2b-r1 — Dispatch muhasebesi ve gerçek toplam deadline

Önkoşul: [E2b inceleme kararı](../E2b-acceptance.md) (kabul edilmedi; 4
bloklayıcı). Ortak kurallar: [worker teslim protokolü](../../issue-05-worker-delivery-protocol.md).
Eski E2b kanıtları (`../E2b/`) değiştirilmedi. E2 kapanmadı; E3/canlı pilot
ilan edilmez.

## Uygulanan davranış

- Zincir sırası üretimde `ThrottledClient(CountingClient(transport))`
  (`scripts/llm_bench.py` dahil): pacing/`Retry-After` redleri rezervasyonun
  üstünde, rezervasyon transport başlangıcının hemen önünde. Reddedilen
  bekleme rezervasyon ve physical dispatch tüketmez (bloklayıcı 1).
- `CountingClient` tek sayaç tutar: `physical_dispatches == reservations ==
  transport starts` (yapı gereği; ayrı reservation sayacı ve iptal
  semantiği yok). Deadline kapısı artırmadan reddeder; `set_deadline`
  artık saklar + zincire iletir. Manifesto/result anahtarı
  `requests` → `physical_dispatches` (bilinçli şema farkı; birim aynı).
- Sayaç denklemleri ledger/attempt olaylarıyla tanımlı (ayrıntı
  `counter-contract.md`): retry'de `physical > evaluations` mümkündür;
  cap-ortası ret `failed(budget)`, `attempts=C+1`, `physical=C`
  (bloklayıcı 2).
- Toplam deadline `HttpLLMClient`'a ulaşır: her dispatch öncesi kalan süre
  hesaplanır, `urlopen` timeout = `min(request_timeout_s, remaining)`;
  süre bitmişse HTTP çağrısı başlamadan terminal deadline (bloklayıcı 3).
- `Retry-After` asla cap'lenmez; `sleep_cap_s` yalnız pacing hook'udur;
  üretim yolunda cap yoktur. Uzun `Retry-After` deadline altında hızlı
  terminal, deadline yokken tamamı uygulanır (sahte saat, gerçek sleep yok).
- Korunanlar: exception-metni minimizasyonu, terminal parse/config, label
  sınırı, outcome karar ayrımı, coverage checker, stability kuralı. E2a/E2b
  testleri güncellendi (zincir sırası + sayaç adı + cap semantiği; açıkça
  değişen 3 beklenti).

## Değişen / yeni dosyalar

- `src/sloplab/experiments/pilot.py`: `CountingClient` (deadline saklama,
  artırmadan ret, `physical_dispatches`), `ThrottledClient` (pacing-only cap,
  uncapped `Retry-After`, gerçek dispatch'te ilerleyen pacing tabanı),
  `_require_counting_client` (zincirden bütçe sahibi bulma).
- `src/sloplab/evaluators/llm/adapter.py`: `HttpLLMClient.set_deadline` +
  kalan-süre timeout hesabı + çağrı-öncesi terminal deadline.
- `src/sloplab/evaluators/llm/failures.py`: koşu-öncesi dispatch reddini de
  kapsayan `DeadlineExceeded` dokümantasyonu (davranış aynı).
- `scripts/llm_bench.py`: üretim zincir sırası, cap'siz `Retry-After`,
  `physical_dispatches` çıktısı.
- Testler: yeni `tests/regression/test_dispatch_accounting.py` (5 kabul
  testi); `test_budget_retry.py`, `test_llm_pilot.py`,
  `test_llm_bench_script.py`, `test_outcomes_ledger.py` (sıra/ad/cap
  güncellemeleri).
- R1 diff'i: `e2b-r1.diff` (başlangıç snapshot'larına karşı, `start/` altında
  8 dosyanın değişim-öncesi kopyası).

## Test / doğrulama

- Yeni 5 kabul testi + ilgili mevcut kümeler geçti; tam offline paket:
  **275 passed** (270 + 5). ruff check/format, mypy temiz. Sıfır canlı
  istek (fake transport + sahte saat + monkeypatch'li `urlopen`).
- Kabul testleri 1–5 `test_dispatch_accounting.py` içindedir (adlarında
  R1 kabul maddesi yazılı); madde 6 tam pakettir.
- Not: `HttpLLMClient` docstring'indeki "canlı ayarlarla test/CI'da
  kullanılmaz" ilkesi korunur — 4. test istemciyi yalnızca sahte API
  anahtarı + yamalanmış `urlopen` ile çevrimdışı kurar, ağa çıkmaz.

## Deterministik study

Yeni benzersiz kök `/tmp/sloplab-e2b-r1-8Z7OOZ` (`E2b-r1` adlandırması;
E2a yolu yeniden kullanılmadı — bloklayıcı 4). Yöntem ve hüküm
`comparisons.md` içinde; ham/semantik eşitlik E1e referansına göre OK.
`/tmp` kalıcı arşiv değildir; kalıcı kanıt bu teslimdeki kopyalardır.
