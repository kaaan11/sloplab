# E5b-r1 — İnceleyici düzeltmesi olmadan kabul

Tarih: 2026-09-10. **E5b-r1 kabul edildi; E5 kapandı.**

## Kapanan bloklayıcı bulgu

`replace_section_body` ve `remove_section` artık varsayılansız
`expected_document_identity` alıyor. `_require_authorized` beklenen kimliği hedef
belgeden yeniden üretmiyor; çağıranın section ile birlikte taşıdığı kaynak
kimliğini hedef belgenin gerçek içerik kimliğiyle karşılaştırıyor.

Üretimdeki 11 splice çağrı noktası incelendi. `evidence`, `impact`, `references`
ve `technical` operatörleri kimliği section'ın çıkarıldığı immediate-parent
belgeden bağlıyor; `ScopeExpansion` ikinci splice öncesinde oluşan metni yeniden
parse edip yeni parent kimliğini kullanıyor. Eksik kimlik argümanı API düzeyinde
`TypeError` ile reddediliyor.

Ana inceleyicinin önceki karşıörneği artık hem replace hem remove yolunda
`StaleSpanError` üretiyor: hedef section'ın metni ve konumu aynı olsa bile tam
belge kimliği farklı foreign parent kabul edilmiyor. Fresh immediate-parent iki
yolda çalışıyor; stale ve grandparent çiftleri reddediliyor.

## Korunan E5b sonucu

`full-item-v1` çok satırlı öğe aralığı, fence/lazy-continuation kontrollü no-op
profili ve RNG davranışı korunmuştur. Yeni deterministik study, E5b ile aynı üç
rapor + üç manifest B1 etki kümesini üretir. 594 evaluator kaydında karar değişimi
yoktur; veri ve analiz etkisi matrisi değişmemiştir. Tarihsel artefaktlara
yazılmamıştır.

Worker kanıtları `docs/reviews/issue-05/E5b-r1/` altında değiştirilmeden
korunuyor. `/tmp/sloplab-e5b-r1-OcoEUQ/run` için teslim edilen 485 satırlık hash
envanteri ana inceleyici tarafından **485/485** yeniden doğrulandı; `/tmp` kalıcı
arşiv değildir.

## Bağımsız doğrulama

- Tam offline pytest paketi ana inceleyici koşusunda exit 0 verdi; worker kabul
  kaydı **404 passed** gösteriyor.
- Değişen beş üretim dosyasında ruff check, ruff format check ve mypy temizdir.
- Doğrudan çağrı envanterinde kimlik argümanı taşımayan üretim splice noktası
  bulunmadı.
- `git diff --check` temizdir.

Sıradaki tek paket: [bütünleşik kapanış doğrulaması](../../issue-05-integration-task.md).
