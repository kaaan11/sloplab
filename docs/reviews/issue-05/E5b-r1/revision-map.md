# E5b-r1 — Revizyon haritası (revision-map.md)

E5b kabul kararındaki bloklayıcı bulgu → R1 karşılığı (dosya + test):

## Tautological kimlik kontrolü

- `_require_authorized` artık beklenen kimliği hedef belgeden
  **türetmiyor**; çağıranın zorunlu `expected_document_identity`
  argümanıyla taşıdığı değeri iletiyor
  (`mutations/textops.py`). İmza değişikliği iki splice yolunda da
  varsayılansız ve atlanamazdır.
- Bütün üretim çağrı noktaları (aramayla doğrulandı, eksik yok)
  kimliği span yakalandığı anda immediate-parent belgeden bağlıyor:
  `evidence.py` (3: repro adımı, repro bütün-bölüm, versions),
  `impact.py` (3: impact, component, reparsed versions),
  `references.py` (4: fabricate, misattribute, preconditions,
  contradict), `technical.py` (1: fallback). Zincirli ikinci splice
  (`ScopeExpansion`) reparsed belgenin kendi kimliğini kullanır.
  `presentation.py` operatörleri splice çağırmaz (düz metin işlemleri;
  denetlendi).
- Eksik argüman `TypeError` üretir (sözleşme testi); tam paketdeki tüm
  operatör çalışmaları yeni imzayla yeşildir (atlanmış nokta kalsaydı
  kırmızı olurdu).

## Karşıörnek kapsamı (hepsi reddedilir)

- İnceleyici karşıörneği (aynı heading/konum/metin, farklı tam belge):
  `test_foreign_span_rejected_on_both_paths` (replace + remove).
- Mutasyon-sonrası eski çift: `test_mutated_span_and_identity_rejected`.
- İkinci nesil grandparent çifti:
  `test_grandparent_span_and_identity_rejected`.
- Fresh immediate-parent çifti iki yolda da çalışır:
  `test_fresh_immediate_parent_succeeds_on_both_paths`.

## Korunan E5b davranışı

- `full-item-v1` aralık, destek profili, fence/lazy no-op, RNG paritesi,
  `span_model` kimliği: `test_b1_fix.py` + `test_source_spans.py`
  aynen yeşil (12 + 20).
- Üç rapor + üç manifesto etki sınırı ve 0-flip matrisi aşağıda
  yeniden üretildi (deterministik study).
