# E5b — Çok satırlı öğe düzeltmesi ve yeni üretim sürümü

Durum: E5b-r1 ile kabul edildi. Son kabul kaydı:
[E5b-r1 kabulü](reviews/issue-05/E5b-r1-acceptance.md). İlk teslimin incelemesi:
[E5b kabul kararı](reviews/issue-05/E5b-acceptance.md). Revizyon görevi:
[E5b-r1](issue-05-E5b-r1-task.md). Önkoşul:
[E5a kabulü](reviews/issue-05/E5a-acceptance.md). Ortak kurallar:
[worker teslim protokolü](issue-05-worker-delivery-protocol.md).

## Hedef

Hedeflenen çok satırlı liste öğesinin tam kaynak aralığını düzenle; devam satırı
ve paragraflarını yetkili öğe kapsamına göre ele alırken komşu kaynak metnini
koru. Düzeltmeyi ayrı üretim/mutation sürümü olarak yayımla; eski türevleri değiştirme.

## Sözleşme

E5a'nın destek profili dışındaki belirsiz girdide kontrollü ret/no-op uygula.
Fence türü/uzunluğu, iç içe/ardışık liste, devam paragrafı, UTF-8 ve satır sonu
testleri profil kadar desteklenir. Stale document identity/span reddedilir. Tek
adımlı parent sınırı korunur; zincirleme veya korpus büyütme eklenmez.

Raporun üç somut örneği ve E5a envanterindeki bütün gerçekten etkilenen türevler
yeniden doğrulanır. Etkiyi metin/vaka sayısı, karar ve metrik katmanlarında ayrı
raporla. Mümkünse eski/yeni veri × eski/yeni analiz matrisi kullan; canlı LLM
gerektiren hücreyi çalıştırılmış gibi sunma.

## Kabul

- Hedef öğe bütünüyle düzenlenir; yetkili aralık dışı kaynak baytları korunur.
- Destek profili ve stale/belirsiz durumlar testlidir.
- Eski artefakt hash'leri değişmez; yeni sürüm açık kimlik taşır.
- E5a envanteri sonuç sayılarıyla uzlaşır.
- Deterministik evaluator/analiz etkisi yeniden üretilebilir ve açıklanır.
- Hedefli ve tam offline paket geçer.

Teslim `b1-fix-contract.md`, `production-impact.md` ve karşılaştırma matrisi içermelidir.
