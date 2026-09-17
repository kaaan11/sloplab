# E5b — B1 düzeltme sözleşmesi (b1-fix-contract.md)

## Hedef davranış (full-item-v1)

`RemoveReproductionStep` tek-adım modunda hedefin **tam kaynak
aralığını** düzenler: adım satırı + girintili devam satırları ve
boşlukla ayrılmış girintili devam paragrafları. Boş satırlar asla
düşürülmez (komşu aralık korunur); kardeş adım/başlık taramayı bitirir.
Üretim sürüm kimliği `full-item-v1`'dir: vaka manifestosunda
(`parameters.span_model`, yalnızca davranışın farklılaştığı vakalarda)
ve defter başlığında (`span_model`) taşınır. Etkilenmeyen vakalar
bayt-eşit kalır.

## Destek profili (dışı ret/no-op)

- Girintili devam (`[ \t]` önekli, adım/başlık/çit olmayan satırlar):
  öğeye dahildir (iç içe alt listeler dahil).
- Bölümde çit işareti varsa: tüm tek-adım işlemi no-op
  (`{"note": "fenced content in section"}`).
- Girintisiz komşu (lazy devam): no-op
  (`{"note": "ambiguous continuation after step N"}`).
- Bayat aralık/yabancı belge: splice kapısı `StaleSpanError` yükseltir
  (`replace_section_body`/`remove_section` girişinde; E5a sözü).
- No-op dalları RNG paritesini korur (`randrange` seçimi +
  `getrandbits(1)` aynen tüketilir): aşağı-akış çekilişi değişmez,
  blast radius hedef vakayla sınırlıdır.
- Tek adımlı parent sınırı korunur (her uygulama doğrudan parenttan
  taze çözer); zincirleme ve korpus büyütme yoktur.

## Korunan kurallar

- Kardeş numaraları yeniden sıralanmaz (mevcut konvansiyon).
- Başlık öneki splice ile geri konur (`offset != 0` kuralı sürer).
- Bütün-bölüm modu, note yolları, RNG akışları değişmedi.
- Eski artefaktlar yeniden üretilmez (hash'ler sabit).
