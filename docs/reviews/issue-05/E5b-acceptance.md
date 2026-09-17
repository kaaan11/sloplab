# E5b — Revizyon gerekli

Tarih: 2026-09-10. **E5b bu teslimle kabul edilmedi. E5 açık kaldı.**

## Doğrulanan kazanımlar

Worker teslimi B1'in üç üretim vakasında hedef adımın girintili devam satırını
kaldırıyor. Kardeş adımlar ve başlık korunuyor; fence veya girintisiz lazy
continuation bulunan profil-dışı girdiler kontrollü no-op oluyor. Üretim etkisi
üç rapor ve bunlara ait üç mutation manifestiyle sınırlı; 594 deterministik
kayıtta karar değişimi yok ve metrik matrisi değişimi veri/formül eksenlerini
ayırıyor.

Worker kayıtlarında 310 hedefli ve 399 tam offline test ile ruff/format/mypy
kontrolleri başarılıdır. Ana inceleyicinin B1 ve source-span kümesi **32/32**
geçti. Worker kanıtları `docs/reviews/issue-05/E5b/` altında değiştirilmeden
korunuyor.

## Bloklayıcı bulgu — splice kapısındaki kimlik kontrolü tautological

E5a kabulünde `span_authorized` için `expected_document_identity` zorunlu hale
getirilmişti. E5b'nin `_require_authorized` kapısı bu kimliği çağırandan veya
span provenance'ından almıyor; doğrudan hedef belgenin kimliğini hesaplayıp aynı
hedef belgeyi doğrularken geri veriyor:

```python
span_authorized(
    document,
    section,
    expected_document_identity=document_identity(document),
)
```

Bu karşılaştırma her zaman hedef belgenin kendi kimliğiyle yapılır ve yabancı
span'ın kaynak kimliğini taşımaz. Bağımsız karşıörnekte iki belgenin hedef bölümü
aynı satır konumu/metin/başlığa, diğer bölümü farklı içeriğe sahipti. Kimlikler
farklı olmasına rağmen yabancı bölüm splice tarafından kabul edildi:

```text
identity_equal= False
foreign_span_authorized= True
replace_section_body= accepted
```

Bu davranış “stale document identity/span reddedilir” sözleşmesini karşılamıyor.
Mevcut test yabancı span'ın yerel metni de farklı olduğu için satır eşitliği
kontrolünde reddediliyor ve kimlik kapısındaki boşluğu gözlemlemiyor.

## Gerekli revizyon

Splice API'si, section ile birlikte yakalanmış kaynak document identity'yi
çağırandan zorunlu olarak almalı veya ikisini ayrılamaz bir authorization nesnesi
olarak taşımalıdır. `replace_section_body` ve `remove_section` bu provenance'ı
yeniden hedef belgeden üretmemeli. Bütün operatör çağrıları kendi immediate-parent
kimliğini span yakalandığı anda bağlamalıdır.

Aynı yerel bölüm baytları ve konumu bulunan fakat tam belge kimliği farklı olan
parent/foreign-parent karşıörneği her iki splice yolunda reddedilmelidir. Fresh
immediate-parent yolu çalışmalı; stale ve ikinci nesil grandparent kimliği
reddedilmelidir. B1 metin davranışı, altı dosyalık üretim etki sınırı ve
`full-item-v1` kimliği korunmalıdır.

Revizyon görevi: [E5b-r1](../../issue-05-E5b-r1-task.md).
