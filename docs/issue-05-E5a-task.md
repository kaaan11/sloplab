# E5a — Kaynak aralığı karakterizasyonu ve düzenleme önkoşulları

Durum: İnceleyici düzeltmesiyle kabul edildi. Kabul kaydı:
[E5a kabulü](reviews/issue-05/E5a-acceptance.md). Önkoşul:
[E4b-r1 kabulü ve E4 kapanışı](reviews/issue-05/E4b-r1-acceptance.md).
Ortak kurallar: [worker teslim protokolü](issue-05-worker-delivery-protocol.md).

## Hedef

B1 davranışını düzeltmeden önce mevcut parser/textops/operator düzenlemelerini
karakterize et. Her düzenleme için kaynak aralığı, belge kimliği/sürümü, parent
sınırı ve önkoşulu açık bir sözleşmeye bağla. E5a çıktısında açıklanmayan türev
bayt farkı sıfır olmalıdır.

## Kapsam

Parser, `models/report.py`, `mutations/textops.py`, liste adımıyla ilgili operator,
materializer ve test fixture'ları incelenir. Raporun üç B1 örneğini ve korpustaki
benzer çok satırlı öğeleri envanterle; örnek sayısını toplam etki sayısı diye
sunma. Fence türü/uzunluğu, devam paragrafı, UTF-8 ve CRLF/LF profilini kaydet.

Eski belge konumunu değişmiş belgeye uygulama reddi ve tek adımlı parent sınırı
testlenir. Bu pakette çok satırlı silme davranışı düzeltilmez, yeni üretim sürümü
çıkarılmaz, zincirleme eklenmez.

## Kabul

- Mevcut davranış golden/characterization testleriyle sabittir.
- Yetkili kaynak aralığı ve belge kimliği precondition'ı makinece doğrulanabilir.
- Stale span, belirsiz syntax ve yanlış parent kontrollü ret/no-op verir.
- E0 referansına karşı üretilen türevlerde açıklanmayan bayt farkı yoktur.
- Toplam etkilenen aday envanteri yöntem ve sınırlamalarıyla teslim edilir.

Teslim `edit-contract.md`, `b1-impact-inventory.md` ve karakterizasyon karşılaştırmasını içerir.
