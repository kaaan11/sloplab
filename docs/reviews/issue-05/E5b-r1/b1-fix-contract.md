# E5b-r1 — B1 düzeltme sözleşmesi (b1-fix-contract.md)

E5b sözleşmesi devralındı; R1 eki yıldızlıdır.

## Hedef davranış (full-item-v1)

`RemoveReproductionStep` tek-adım modunda hedefin **tam kaynak
aralığını** düzenler: adım satırı + girintili devam satırları ve
boşlukla ayrılmış girintili devam paragrafları. Boş satırlar asla
düşürülmez; kardeş adım/başlık taramayı bitirir. Üretim sürüm kimliği
`full-item-v1`'dir (davranış farklılaşan vaka manifestolarında +
defter başlığında).

## ★ Kaynak kimliğine bağlı splice authorization

- `replace_section_body` / `remove_section`, section ile birlikte
  yakalanmış kaynak `document_identity` değerini **zorunlu**
  `expected_document_identity` argümanıyla alır (varsayılan yok,
  atlanamaz). Kapı kimliği hedeften yeniden üretmez; beklenen değerle
  hedefin gerçek baytlarını karşılaştırır.
- Üretim operatörleri kimliği span yakalandığı anda immediate-parent
  belgeden bağlar (evidence 3, impact 3, references 4, technical 1
  çağrı noktası; zincirli splice reparsed kimliği kullanır).
- Taze immediate-parent çifti çalışır; yabancı/bayat/grandparent
  çifti `StaleSpanError` ile reddedilir. Hata, kontrollü ret
  sözleşmesiyle uyumludur (defterde error satırı olur, sessiz değil).

## Destek profili ve sınırlar (değişmedi)

- Bölümde çit işareti → no-op; girintisiz komşu → no-op; RNG paritesi
  korunur. Kardeş numaralandırma, başlık öneki, bütün-bölüm/note
  yolları aynıdır. Tek adımlı parent sınırı sürer; zincirleme ve
  korpus büyütme yoktur. Eski artefaktlar yeniden üretilmez.
