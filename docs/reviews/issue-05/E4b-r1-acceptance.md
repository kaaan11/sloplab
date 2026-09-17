# E4b-r1 — İnceleyici düzeltmesiyle kabul ve E4 kapanışı

Tarih: 2026-09-10. **E4b-r1, ana inceleyici düzeltmesinden sonra kabul edildi. E4 kapatıldı.**

## Karar

E4b-r1 sürümlü analiz zarfını şema 2'ye çıkararak records yanında outcomes
varlık/yol/hash/satır bağını taşıyor. Evaluator başına planned, scored, failed ve
not_run sayaçları yayın sırasında uzlaştırılıyor; okuyucu records, outcomes ve
suite index üzerinden evaluator kümesini, vaka birliğini, tekilliği ve sayaçları
yeniden türetiyor.

Tamamen başarısız evaluator `scored=0`, `failed=N` ve tanımsız metrik nedenleriyle
analizde korunuyor. Gömülü E4a metric bundle'ları bağlı records üzerinden güncel
analiz tanımıyla yeniden hesaplanıyor; coverage veya metric değişikliği completion
yenilense bile reddediliyor. Tarihsel `analysis.json`, estimand, ağırlık ve CI
tercihleri değiştirilmedi.

## İnceleyici düzeltmesi

Zarfın `evaluators` alanı küme karşılaştırmasında iterable olarak kullanıldığı
için aynı anahtarları taşıyan bir JSON nesnesi, gerekli liste şeklinin yerine
kabul edilebiliyordu. Bağımsız karşıörnekte alan
`{"evidence-graph-baseline": true, "rules-baseline": true}` biçimine çevrilip
completion yenilendiğinde okuyucu belgeyi kabul etti.

Okuyucu artık `evaluators` alanını sıralı, tekil, boş olmayan string listesi olarak
doğruluyor. Yeni regresyon testi nesne biçimini tazelenmiş completion ile reddediyor.
Worker'ın `docs/reviews/issue-05/E4b-r1/` kanıtları değiştirilmeden korunuyor.

## Bağımsız doğrulama

- Worker kayıtları: 258 hedefli ve 366 tam offline test; ruff, format ve mypy
  başarılı; teslim run envanteri 485/485 doğrulanmış.
- İnceleyici düzeltmesi sonrası analysis binding/version/history/operator kümesi:
  **27/27**.
- Tam offline paket: **367/367**.
- Ruff, format, mypy ve `git diff --check`: temiz.
- Yeni deterministik review çalışması:
  `/tmp/sloplab-e4b-r1-review-RVW001/run`; 297 vaka, iki evaluator ve 594 kayıt.
  Worker koşusuyla 485 dosyalık küme aynı, 483 dosya ham eşit. Yalnız izinli
  zaman alanlarını taşıyan `manifest.json` ve onun hash'ini taşıyan
  `completion.json` farklı; sürümlü analiz dahil diğer dosyalar eşit. Strict
  bundle ve versioned-analysis doğrulaması başarılıdır. `/tmp` kalıcı arşiv değildir.

## E4 kapanış sınırı

E4a ile metrik uygunluğu, paired susceptibility, ECE ve repeat-scoped parent
bağları; E4b serisiyle analiz sürümü, kaynak hashleri, selection/outcome coverage,
tarihsel yeniden hesaplama ve operatör uygunluğu kapandı.

Kaynak metin aralıkları ve B1 çok satırlı düzenleme davranışı E5 kapsamındadır.
Canlı pilot henüz başlatılabilir ilan edilmedi. Sıradaki paket
[E5a görev dosyasıdır](../../issue-05-E5a-task.md).
