# E2b-r2 — Tek yürütme zinciri ve yarışsız dispatch muhasebesi

Durum: Ana inceleyici düzeltmesiyle kabul edildi. Kabul:
[E2b-r2 kabul kaydı](reviews/issue-05/E2b-r2-acceptance.md).
Kök: `/home/kaan/sloplab`. Yürütücü: worker model.
Önkoşul: [E2b-r1 inceleme kararı](reviews/issue-05/E2b-r1-acceptance.md).
Ortak kurallar: [worker teslim protokolü](issue-05-worker-delivery-protocol.md).

## Tek hedef

E2b-r1'in doğrulanmış işlerini koru. Config'ten pacing/deadline zincirini tek bir
pilot yürütme sınırında kur veya doğrula; deadline kontrol yarışında başlamayan
transport'u physical/error saymadan hard cap'i koru.

## Zorunlu sözleşme

- `run_llm_pilot` ve `scripts/llm_bench.py` aynı client-chain kurucusunu veya aynı
  açık doğrulayıcıyı kullanmalı. `min_interval_ms`, deadline ve hard cap değerleri
  config'ten ayrışamaz. Bare/misordered/double `CountingClient` ya normalize edilmeli
  ya da herhangi bir dispatch öncesi açıklayıcı config hatasıyla reddedilmelidir.
- Script'in özel wrapper kurması doğrudan pilotta atlanabilen ikinci bir politika
  yolu oluşturmamalı. Test helper'ları da production ile aynı kurulum yolunu kullansın.
- Hard cap tek-thread ortamda dispatch öncesi rezerve edilir. İç transport
  pre-dispatch `DeadlineExceeded` verirse rezervasyon tüketilmemiş sayılır;
  `physical_dispatches`, `errors` ve `timeouts` artmaz. Transport gerçekten
  başladıktan sonraki success/timeout/429/transport error physical sayılır.
- Deadline'ın iki ardışık saat okuması arasında bitmesi deterministic fake-clock
  testiyle kapsansın. Contract bu yarışı istisna olarak dışarıda bırakmasın.
- `HttpLLMClient` kalan-süre timeout'u, uncapped production `Retry-After`, terminal
  parse/config, outcome/label sınırı ve E2b coverage denetimi korunmalı.
- Sayaç ve wrapper şeması değişirse script, result, manifest, test ve sözleşme
  belgeleri birlikte güncellenmeli; legacy bundle okuma E3'e bırakılmalı.

## Kabul testleri

1. İki saat kontrolü: outer check deadline öncesi, HTTP check deadline sonrası;
   `urlopen_calls=0`, `physical_dispatches=0`, `errors=0`.
2. Doğrudan pilotta `min_interval_ms=500`, iki gerçek dispatch arasında sahte
   saatte tam pacing üretir. Aynı config ile script ve direct sayaç/uyku davranışı
   aynı yürütme kurulumundan gelir.
3. Yanlış sıralı, çift budget-owner veya config'ten farklı pacing zinciri dispatch
   öncesi reddedilir ya da canonical biçime güvenli normalize edilir; sessiz bypass yoktur.
4. Success-after-retry `evaluations=1`, `attempts=3`, `physical=3`; cap-in-retry
   ve pacing/Retry-After deadline yolları önceki exact değerleri korur.
5. HTTP remaining-time timeout ve uzun `Retry-After` testleri geçer; ağ/gerçek sleep yoktur.
6. E2a, E2b ve E2b-r1 hedefli testleri ile tam offline paket geçer.

## Teslim

Kanıt dizini `docs/reviews/issue-05/E2b-r2/` olmalıdır. Önceki E2b/E2b-r1
kanıtlarını değiştirme. `execution-chain-contract.md`, wrapper sahipliği ve
dispatch olay sırasını; `counter-contract.md`, exact sayaç geçişlerini anlatsın.
Yeni deterministic study benzersiz `/tmp/sloplab-e2b-r2-XXXXXX` kökünde üretilsin;
E1e referansına karşı ham/semantik farklar doğrulansın.

E2'nin kapanışını yalnız ana inceleyici kabul kaydı belirler. E3 veya canlı pilot
hazır ilan edilmez.
