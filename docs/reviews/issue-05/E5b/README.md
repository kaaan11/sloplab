# E5b — Çok satırlı öğe düzeltmesi ve yeni üretim sürümü

Önkoşul: [E5a kabulü](../E5a-acceptance.md) (inceleyici düzeltmeli).
Ortak kurallar: [worker teslim protokolü](../../issue-05-worker-delivery-protocol.md).
Önceki kanıtlar değiştirilmedi. Canlı pilot ilan edilmedi.

## Uygulanan davranış

- `full_step_span`: hedef adım + girintili devam satır/paragrafları;
  boş satırlar korunur, kardeş adım bitirir; çit/başlık/girintisiz
  komşuda `None` (kontrollü no-op). `RemoveReproductionStep` tam
  aralığı düşürür; profil-dışı girdide RNG pariteli no-op verir.
- Splice kapısı: `replace_section_body`/`remove_section` girişte
  `span_authorized` ister; bayat/yabancı aralık `StaleSpanError`
  yükseltir (defterde error satırı olur, sessiz değil).
- Sürüm kimliği `full-item-v1`: davranış farklılaşan vaka
  manifestolarında (`span_model` + `removed_extra_lines`) ve defter
  başlığında. Paket sürümü değişmedi; eski artefaktlar üretilmedi.
- Korunanlar: kardeş numaralandırma, başlık öneki, bütün-bölüm/note
  yolları, RNG akışları, tek-adımlı parent sınırı (zincirleme/korpus
  büyütme yok).

## Değişen / yeni dosyalar

- `mutations/textops.py` (kapı + aralık + ayna regexler),
  `mutations/operators/evidence.py` (tam-aralık + profil + kimlik),
  `mutations/materialize.py` (defter başlığı).
- Yeni testler (12): `tests/regression/test_b1_fix.py`.
- E5a test güncellemeleri (3): kalıntı goldeni → tam-kaldırma,
  ikinci-nesil kalıntı iddiası kalktı, committed-karşılaştırma →
  etki-uzlaşma (yalnız B1 dosyaları farklı).
- Belgeler: `b1-fix-contract.md`, `production-impact.md` (+ matris).

## Test / doğrulama

- Hedefli küme: **310 passed**. Tam offline paket: **399 passed**
  (387 + 12). ruff check/format, mypy temiz. Sıfır canlı istek.
- Etki: 6 dosya (3 rapor kalıntı-satır silme + 3 manifesto kimliği);
  594 kayıtta 0 karar değişimi; metrikler birebir aynı; llm-pilot
  hücreleri çalıştırılmadı (canlı API gerekir — sunulmuyor).

## Deterministik study

Yeni benzersiz kök `/tmp/sloplab-e5b-VbclxH` (297 cases, 2 evaluators;
594 kayıt). E1e'ye göre: üç şema eki + iki devralınmış türev + B1 etki
kümesi (6 dosya + 2 türev hash); ortak 472 hash IDENTICAL. Yeni paket
`complete` (485 dosya); `run-outputs.sha256` 485/485 doğrulandı. `/tmp`
kalıcı arşiv değildir.
