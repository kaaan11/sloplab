# E5b-r1 — Kaynak kimliğine bağlı splice authorization

Durum: Kabul edildi. Kabul kaydı:
[E5b-r1 kabulü](reviews/issue-05/E5b-r1-acceptance.md). Önkoşul:
[E5b revizyon kararı](reviews/issue-05/E5b-acceptance.md). Ortak kurallar:
[worker teslim protokolü](issue-05-worker-delivery-protocol.md).

## Hedef

E5b'nin full-item-v1 çok satırlı adım düzeltmesini, destek profilini, üretim etki
sınırını ve veri/analiz matrisini koru. Splice kapısını section'ın yakalandığı
belgenin kimliğine gerçekten bağla; hedef belgeden yeniden üretilen tautological
kimlik kontrolünü kaldır.

## Bloklayıcı karşıörnek

İki belgenin hedef bölümü aynı heading, source location ve section text değerine,
fakat başka bölümde farklı içeriğe sahip olsun. `document_identity` değerleri
farklıdır. Mevcut `_require_authorized`, hedef belgenin kimliğini yine hedef
belgeye verdiği için foreign section `replace_section_body` tarafından kabul
edilir.

## Bağlayıcı sözleşme

- Section/span yakalandığında aynı kaynak belgenin `document_identity` değeri de
  yakalanmalı ve splice çağrısına zorunlu taşınmalıdır; kapı beklenen kimliği
  hedef belgeden kendiliğinden türetmemelidir.
- API, kaynak kimliğini ayrı ve zorunlu bir argümanla alabilir veya section ile
  kimliği ayrılamaz bir authorization değeri içinde taşıyabilir. Seçilen biçim
  hem `replace_section_body` hem `remove_section` için aynı güvenceyi vermelidir.
- Bütün üretim çağrı noktaları (`evidence`, `impact`, `references`, `technical`
  ve aramayla bulunan diğerleri) section'ı çıkardıkları immediate-parent
  belgenin kimliğini aynı anda bağlamalıdır.
- Fresh immediate-parent section/kimlik çifti çalışmalıdır. Aynı yerel section
  baytları ve konumu bulunan foreign parent; stale parent ve ikinci nesil
  grandparent section/kimlik çiftleri splice edilmeden reddedilmelidir.
- Kimlik denetimi atlanabilir veya varsayılan bir argüman olmamalıdır. Hata,
  mevcut kontrollü ret sözleşmesiyle uyumlu ve test edilebilir olmalıdır.

## Korunacak E5b davranışı

- `full-item-v1` çok satırlı öğe aralığı, destek profili ve fence/lazy
  continuation no-op davranışı değişmemelidir.
- Aynı deterministik RNG ve çalışma girdileriyle üretim etkisi tam olarak üç
  rapor ile bunlara ait üç mutation manifestinde kalmalıdır; eski artefaktlar
  değiştirilmemelidir.
- Vaka ve evaluator kayıt sayıları korunmalı; beklenen karar değişimi sıfırdır.
  Veri/formül etkisini ayıran eski/yeni veri × eski/yeni analiz matrisi aynı
  sonuçlarla yeniden üretilebilmelidir.
- Zincirleme mutasyon, korpus büyütme veya canlı API çağrısı eklenmemelidir.

## Zorunlu testler

- Aynı heading, source location ve section text; farklı tam belge içeriği olan
  iki parent ile hem replace hem remove yolu reddedilir.
- Fresh immediate-parent ile her iki splice yolu başarılıdır.
- Mutasyondan sonra eski section/kimlik ve grandparent section/kimlik kullanımı
  reddedilir.
- Tüm üretim operatörleri yeni zorunlu sözleşmeden geçer; doğrudan splice çağrı
  noktası eksik kalmadığı aramayla ve testle gösterilir.
- E5b'nin B1 regresyon, destek profili, deterministik üretim ve tam offline test
  kümeleri geçer; ruff, format ve mypy kontrolleri çalıştırılır.

## Teslim ve kanıt

Teslimi `docs/reviews/issue-05/E5b-r1/` altında sakla. `README.md` şunları
bağlamalıdır:

- değişen dosyalar ve kısa gerekçe;
- çalıştırılan komutların tam metni, exit code ve sonuç özeti;
- karşıörnek ile fresh/stale/grandparent test kanıtı;
- deterministik çalışma yolu, girdi/çıktı kimlikleri ve eski artefakt hash
  değişmezliği;
- üç rapor + üç manifest etki envanteri, karar sayıları ve analiz matrisi;
- `revision-map.md` içinde bu briefteki her zorunluluğun kod/test/kanıt eşlemesi;
- güncellenmiş `b1-fix-contract.md` ve gerekiyorsa `production-impact.md`.

Worker çıktıları ve logları bu dizinde belge olarak korunmalıdır. Ana inceleyici
teslimi bağımsız olarak doğrulayacak; worker'ın kabul beyanı tek başına yeterli
değildir.
