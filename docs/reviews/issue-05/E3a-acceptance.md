# E3a — İnceleyici düzeltmesiyle kabul

Tarih: 2026-09-10. **E3a, ana inceleyici düzeltmesinden sonra kabul edildi.**

## Karar

Worker teslimi study ve LLM pilot yayın sınırlarına deterministik
`completion.json` işareti ekliyor. İşaret paket türünü ve kendisi dışındaki tam
dosya kümesinin SHA-256 değerlerini taşıyor. `verify_bundle` eksik, fazla,
karışmış veya hash'i değişmiş dosyaları ve tür uyuşmazlığını reddediyor;
işaretsiz tarihsel paketler dönüştürülmeden legacy olarak sınıflanıyor.

Yazıcı ve okuyucu envanteri, cache edilmiş çıktıların durumu ve dosya başına
rename sınırı teslim belgelerinde açıklandı. Worker kanıtları
`docs/reviews/issue-05/E3a/` altında değiştirilmeden korunuyor.

## İnceleyici düzeltmesi

İlk uygulama mevcut bir çıktı dizinine yeniden yazarken eski
`completion.json` dosyasını yeni çalışmanın sonuna kadar yerinde bırakıyordu.
Böylece ikinci çalışma başlamış olmasına rağmen eski paket, ilk içerik değişene
kadar strict reader'a tamamlanmış görünebiliyordu. Bu durum işaretin her yayın
döngüsünde en son görünür olması sözleşmesine aykırıydı.

`invalidate_completion` eklendi. Pilot eski işareti herhangi bir model
dispatch'inden önce, CLI study ise runner çıktılarını yazmadan önce kaldırıyor.
Pilot ve study için aynı dizine yeniden yazma regresyon testleri, çalışma
sırasında paketin `complete` görünmediğini ve başarılı yayın sonunda yeniden
doğrulandığını sabitliyor.

## Bağımsız doğrulama

- Worker kayıtları: 166 hedefli ve 296 tam offline test; ruff, format ve mypy
  başarılı; teslim run envanteri 483/483 doğrulanmış.
- İnceleyici düzeltmesi sonrası E3a testleri: **19/19**.
- İlgili study, execution-chain ve outcome kümesi: **49/49**.
- Tam offline paket: **298/298**.
- Ruff, format, mypy ve `git diff --check`: temiz.
- Yeni deterministik review çalışması:
  `/tmp/sloplab-e3a-review-Epaw0B/run`; 297 vaka, iki evaluator ve 594 kayıt.
  Worker E3a çalışmasıyla 483 dosyalık küme aynı, 481 dosya ham eşit. Yalnız
  izinli zaman alanlarını taşıyan `manifest.json` ve onun hash'ini taşıyan
  `completion.json` farklı; diğer completion içeriği eşit. Strict doğrulama
  başarılıdır. `/tmp` kalıcı arşiv değildir.

## Kapsam sınırı

E3a yeni şemanın completion işaretini ve strict doğrulama çekirdeğini kabul
eder. Tüketicilerin strict/legacy geçişi, materialization outcome defteri ve
coverage ayrımı E3b kapsamındadır. E3 henüz kapanmadı; canlı pilot henüz
başlatılabilir ilan edilmedi. Sıradaki paket [E3b görev dosyasıdır](../../issue-05-E3b-task.md).
