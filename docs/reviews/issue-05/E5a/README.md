# E5a — Kaynak aralığı karakterizasyonu ve düzenleme önkoşulları

Önkoşul: [E4b-r1 kabulü ve E4 kapanışı](../E4b-r1-acceptance.md). Ortak
kurallar: [worker teslim protokolü](../../issue-05-worker-delivery-protocol.md).
Önceki kanıtlar değiştirilmedi. Canlı pilot ilan edilmedi.

## Uygulanan iş (davranış değişikliği yok)

- Yeni `textops.span_authorized` + `document_identity` (salt doğrulama;
  operatörler çağırmaz): konum sınırları + ham bayt eşitliği + başlık
  ayrıştırması. Korpusun 560 ayrıştırılmış bölümü tamamı doğrulanır.
- 20 golden karakterizasyon testi (`test_source_spans.py`): B1 kalıntısı
  (totiming-019, tohum 21, bayt-seviyesi), bütün-section/note yolları,
  adım regex kenarları, çit kuralları (tür/uzunluk/karışık/kapanmamış),
  CRLF normalleşmesi, UTF-8 geçişi, boşluk yutma, başlık koruma,
  bayat/yanlış-parent bipartit retleri, tek-adımlı parent sınırı,
  committed-paket bayt karşılaştırması.
- Davranış diff'i yalnız eklenen yardımcıdır (27 satır); türev üreten
  hiçbir satır değişmedi.

## Kabul karşılığı

- Mevcut davranış golden'larla sabit (20 test).
- Yetkili aralık + belge kimliği önkoşulu makinece doğrulanabilir
  (`span_authorized` + testleri).
- Bayat aralık ret, belirsiz syntax sabitlenmiş kısıt, yanlış parent
  note no-op verir (operatör-içi zorlama E5b'nindir — açıkça belgeli).
- E0 referansına karşı açıklanmayan türev bayt farkı: sıfır (474 dosya +
  index gövdesi).
- Aday envanteri yöntem/sınırlarıyla teslimde (3 örnek + 18 fixtureda 20
  devam satırı; sayı toplam etki diye sunulmadı).

## Test / doğrulama

- Hedefli küme: **279 passed**. Tam offline paket: **387 passed**
  (367 + 20). ruff check/format, mypy temiz. Sıfır canlı istek.

## Deterministik study

Yeni benzersiz kök `/tmp/sloplab-e5a-PTqVq6` (297 cases, 2 evaluators;
594 kayıt). E1e'ye göre: üç şema eki + iki devralınmış türev; ortak 478
hash IDENTICAL. Yeni paket `complete` (485 dosya); `run-outputs.sha256`
485/485 doğrulandı. `/tmp` kalıcı arşiv değildir.
