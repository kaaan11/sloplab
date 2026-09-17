# E2b-r2 — Tek yürütme zinciri ve yarışsız dispatch muhasebesi

Önkoşul: [E2b-r1 inceleme kararı](../E2b-r1-acceptance.md) (kabul edilmedi; 2
bloklayıcı). Ortak kurallar: [worker teslim protokolü](../../issue-05-worker-delivery-protocol.md).
E2b/E2b-r1 kanıtları değiştirilmedi. E2 kapanmadı; E3/canlı pilot ilan edilmez.

## Uygulanan davranış

- Deadline yarışı kapatıldı (bloklayıcı 1): inner pre-dispatch
  `BudgetExhausted`/`DeadlineExceeded` transport başlamadı demektir;
  `CountingClient` rezervasyonu iade eder (`physical -= 1`), `errors` ve
  `timeouts` artmaz, hard cap korunur. İki kontrollü saat testi:
  `urlopen=0`, `physical=0`, `errors=0`; aynı cap ile sonraki dispatch
  başarabilir. Contract yarışı istisna saymaz.
- Tek yürütme sınırı (bloklayıcı 2): `build_pilot_client_chain` ortak
  kurucudur — `llm_bench.py`, pilot test helper'ları ve yeni testler aynı
  yolu kullanır. `run_llm_pilot` zinciri dispatch öncesi doğrular:
  çıplak `CountingClient` config pacing ile normalize edilir (doğrudan
  pilot, script ile aynı pacing/deadline/cap'i uygular); yanlış sıralı,
  çift sahipli, yabancı wrapper'lı veya pacing'i config'ten ayrışan zincir
  açıklayıcı `ValueError` ile reddedilir (dispatch öncesi, sayaç 0).
- Korunanlar: E2b-r1 işleri (kalan-süre HTTP timeout, uncapped production
  `Retry-After`, `physical_dispatches` sayacı, 5 test), terminal
  parse/config, outcome/label sınırı, E2b coverage denetimi. Şema değişmedi;
  legacy bundle okuma E3'te.

## Değişen / yeni dosyalar

- `src/sloplab/experiments/pilot.py`: rollback (`physical -= 1`, errors/
  timeouts yok), `build_pilot_client_chain`, `_normalize_pilot_chain`,
  `_min_interval_ms` saklama, pilot-içi bağlama (çağıran değişmez).
- `scripts/llm_bench.py`: ortak kurucu (özel wrapper kurulumu kalktı).
- Testler: yeni `tests/regression/test_execution_chain.py` (4 kabul testi:
  yarış, doğrudan-pilot pacing, script-kurucu casusu, 4'lü ret);
  `test_dispatch_accounting.py` (ortak kurucu + `strftime`/`gmtime` saati),
  `test_budget_retry.py` (ortak kurucu), `test_llm_pilot.py` (bütçe
  testlerinde pacing sıfırlama — odak dışı gerçek uykuları önler).
- R2 diff'i: `e2b-r2.diff` (başlangıç snapshot'larına karşı, `start/` altında
  9 dosyanın değişim-öncesi kopyası; yeni test dosyası başlıkta kayıtlı).

## Test / doğrulama

- Hedefli küme: **141 passed** (137 + 4 yeni). Tam offline paket:
  **279 passed** (275 + 4). ruff check/format, mypy temiz. Sıfır canlı
  istek (fake transport + sahte saatler + yamalanmış `urlopen`).
- Kabul maddeleri 1–3 `test_execution_chain.py` içindedir; 4–5 önceki exact
  testlerle (`test_dispatch_accounting.py`) korunur; 6 tam pakettir.

## Deterministik study

Yeni benzersiz kök `/tmp/sloplab-e2b-r2-PnuvGm` (R2 adlandırması; E1e/E2a
yolları yeniden kullanılmadı). Yöntem ve hüküm `comparisons.md` içinde;
ham/semantik eşitlik E1e referansına göre OK. `/tmp` kalıcı arşiv değildir;
kalıcı kanıt bu teslimdeki kopyalardır.
