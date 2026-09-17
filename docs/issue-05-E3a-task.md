# E3a — Bundle envanteri, tamamlanma işareti ve doğrulayan okuyucu

Durum: İnceleyici düzeltmesiyle kabul edildi. Kabul kaydı:
[E3a kabulü](reviews/issue-05/E3a-acceptance.md). Önkoşul:
[E2b-r2 kabulü ve E2 kapanışı](reviews/issue-05/E2b-r2-acceptance.md).
Ortak kurallar:
[worker teslim protokolü](issue-05-worker-delivery-protocol.md).

## Hedef

Study, pilot, CLI `compare`, raporlama ve cache edilmiş analiz dahil bütün bundle
yazıcı/okuyucularını envanterle. Yeni şema için ortak bir completion manifesti ve
doğrulayıcı reader sınırı kur: gerekli dosyalar ile hash'ler tamamlanmadan çalışma
tamamlanmış görünmesin; okuyucu eksik, stale, karışmış veya hash'i bozuk paketi
reddetsin.

## Sınırlar

`experiments/runner.py`, `study.py`, `pilot.py`, CLI ve reporting tüketicileri ile
ilgili modeller/testler değişebilir. Aynı filesystem içindeki staging→publish
varsayımını açıkla; dosya başına rename'i bütün bundle atomikliği diye sunma.
Completion marker en son yayımlanmalı ve gerekli dosya kümesi/hash'lerini taşımalı.
Reader completion marker yokken yeni bundle'ı kabul etmemeli.

Legacy bundle'ı otomatik dönüştürme. Bu pakette yalnız yeni şema strict yolu ve
legacy'nin nasıl tanınacağı belirlenir; ayrıntılı legacy tüketimi E3b'dir.
Metrikleri yeniden hesaplama E4, materialization durum defteri E3b kapsamıdır.

## Kabul

- Her writer/reader envanterde ve sahiplik tablosunda bulunur.
- Her yazım sınırında fault injection eksik bundle üretir; strict reader reddeder.
- Dosya değişimi, iki run dosyasının karıştırılması ve hash uyuşmazlığı reddedilir.
- Completion marker son dosyadır; başarılı publish bütün iç hash'lerle açılır.
- Study ve pilot outcome/identity/recipe dosyaları kendi gerekliliklerine göre kapsanır.
- Eski artefaktlar değiştirilmez; tam offline paket geçer.

Teslim `bundle-contract.md` ve `writer-reader-inventory.md` içermelidir.
