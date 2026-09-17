# E2b-r1 — Ana inceleyici kararı: ikinci revizyon gerekli

Tarih: 2026-09-09. **E2b-r1 kabul edilmedi; E2b-r2 revizyonu gerekli.**

## Doğrulanan ilerleme

Worker önceki dört bulguyu hedefleyen ayrı kanıt paketi hazırladı. Üretim zinciri
`ThrottledClient(CountingClient(transport))` sırasına çevrilmiş, manifest sayaç adı
`physical_dispatches` olmuş, HTTP timeout kalan deadline ile sınırlandırılmış ve
production `Retry-After` cap'i kaldırılmış. Benzersiz
`/tmp/sloplab-e2b-r1-8Z7OOZ/run` kullanılmış; E1e referansına karşı 482 dosyalık
küme ve 480 ham veri/identity dosyası eşit, yalnız zaman alanları farklıdır.

Worker kanıtında 137 hedefli ve 275 tam offline test, ruff/format/mypy ve
karşılaştırma exit 0'dır. Ana inceleyici yeni beş kabul testini yeniden çalıştırdı;
hepsi geçti. Run hash envanteri doğru çalışma kökünde bağımsız olarak 482/482
doğrulandı ve `git diff --check` temizdir.

## Bloklayıcı bulgular

### 1. Deadline yarışında fiziksel sayaç hâlâ yanlış

`CountingClient.complete()` kendi deadline kontrolünden sonra
`physical_dispatches` değerini artırıyor. Ardından `HttpLLMClient.complete()` aynı
deadline'ı yeniden kontrol ediyor. Deadline bu iki kontrol arasında biterse HTTP
dispatch başlamadan `DeadlineExceeded` yükseliyor; sayaç ve error yine artıyor.

Worker'ın `counter-contract.md` belgesi bu durumu “gerçek saatte deadline'ın iki
okuma arasına düşmesi gibi kaybolacak kadar dar yarış dışında” diyerek dışarıda
bırakıyor. Görev exact muhasebe istediği için yarışın dar olması istisna değildir.
Ana inceleyici iki kontrollü saatle şu sonucu üretti:

```text
DeadlineExceeded
physical_dispatches 1 urlopen_calls 0 errors 1
```

Sayaç gerçek transport başlangıcını ancak inner çağrının pre-dispatch
`DeadlineExceeded` sonucunu ayırarak veya tek bir hazırlama/başlatma sınırı kurarak
saymalıdır. Tek-thread hard cap korunmalı; başlamayan deneme physical/error değildir.

### 2. Doğrudan pilot config pacing'ini uygulamıyor

`min_interval_ms` yalnız `scripts/llm_bench.py` içinde `ThrottledClient`
oluşturulurken uygulanıyor. `run_llm_pilot()` evaluator client zincirinde bir
`CountingClient` buluyor fakat config'teki pacing ile wrapper'ın varlığını/değerini
kurmuyor veya doğrulamıyor. Doğrudan pilot çağrısı bare `CountingClient` ile aynı
config'i sessizce farklı uygular.

Ana inceleyici, `min_interval_ms=500` ve iki vaka ile doğrudan pilot yolunda şunu
doğruladı:

```text
config_min_interval_ms 500 transport_calls 2 recorded_sleeps [] physical_dispatches 2
```

Bu, E2b kabulündeki “script ve doğrudan pilot aynı execution/muhasebe yolunu
kullanır” koşulunu bozuyor. Pacing/deadline wrapper sahipliği pilot yürütme
sınırında merkezileştirilmeli veya yanlış zincir dispatch öncesi açıkça
reddedilmelidir; config sessizce yok sayılamaz.

## Korunacak işler ve karar

E2b-r1'in benzersiz run provenance'ı, kalan-süre HTTP timeout'u, uncapped
`Retry-After`, yeniden adlandırılmış manifest sayacı ve beş testi korunabilir.
Worker'ın `docs/reviews/issue-05/E2b-r1/` kanıtları değiştirilmez.

Sorunlar birden fazla client katmanının sahipliğini etkilediği için ana inceleyici
küçük patch uygulamadı. Sıradaki çalışma
[E2b-r2 görev dosyasıdır](../../issue-05-E2b-r2-task.md). E2 kapanmadı; E3 ve canlı
pilot için kabul verilmedi.
