# E5a — İnceleyici düzeltmesiyle kabul

Tarih: 2026-09-10. **E5a, ana inceleyici düzeltmesinden sonra kabul edildi.**

## Karar

E5a mevcut satır-bazlı liste düzenleme davranışını değiştirmeden karakterize
ediyor. B1'in üç rapor örneği ve canonical korpustaki adaylar envanterlendi;
18 fixture içindeki 20 devam satırı aday olarak ayrıldı ve bu sayı gerçek etki
sayısı olarak sunulmadı. Fence, continuation, UTF-8 ve CRLF/LF davranışları
golden testlerle sabitlendi.

Kaynak konumu, bölüm metni/başlığı ve tam belge içerik kimliği için salt doğrulama
yardımcıları eklendi. Üretim operatörleri bu pakette değiştirilmedi. Worker'ın
materyalizasyon karşılaştırmasında 474 türev dosya committed paketle bayt-eşit;
suite-index gövdesi aynı ve yalnız izinli corpus-root başlık farkı var.

## İnceleyici düzeltmesi

Worker'ın `span_authorized` yardımcısı document identity'yi kontrol etmiyordu.
İki belgenin hedef bölümü aynı satır konumu, başlık ve metne sahip olup başka bir
bölümü farklıysa kimlikler farklı olmasına rağmen yabancı span yetkili kabul
ediliyordu:

```text
identity_equal= False
foreign_span_authorized= True
```

`expected_document_identity` artık `span_authorized` için zorunlu keyword
argümanıdır ve tam belge hash'i eşleşmeden aralık yetkilendirilmez. Korpus sweep,
stale span, wrong-parent, crafted span, preamble ve tek-adımlı parent testleri
yeni sözleşmeye geçirildi. Aynı yerel span'a sahip farklı parent karşıörneği için
ayrı regresyon testi eklendi. Worker'ın `docs/reviews/issue-05/E5a/` kanıtları
değiştirilmeden korunuyor.

## Bağımsız doğrulama

- Worker kayıtları: 279 hedefli ve 387 tam offline test; ruff, format ve mypy
  başarılı; teslim run envanteri 485/485 doğrulanmış.
- İnceleyici düzeltmesi sonrası kaynak-span testleri: **21/21**.
- Tam offline paket: **388/388**.
- Ruff, format, mypy ve `git diff --check`: temiz.
- Yeni deterministik review çalışması:
  `/tmp/sloplab-e5a-review-RVW001/run`; 297 vaka, iki evaluator ve 594 kayıt.
  Worker çalışmasıyla 485 dosyalık küme aynı, 483 dosya ham eşit. Yalnız izinli
  zaman alanlarını taşıyan `manifest.json` ve onun hash'ini taşıyan
  `completion.json` farklı; diğer bütün dosyalar eşit. Strict bundle ve sürümlü
  analiz doğrulaması başarılıdır. `/tmp` kalıcı arşiv değildir.

## Kapsam sınırı

E5a yalnız mevcut düzenleme davranışını ve authorization önkoşullarını
karakterize eder. Çok satırlı öğenin tam aralıkla kaldırılması, belirsiz syntax
reddi, operatör-içi kimlik/span zorlaması, yeni üretim sürümü ve etki matrisi E5b
kapsamındadır. Sıradaki paket [E5b görev dosyasıdır](../../issue-05-E5b-task.md).
