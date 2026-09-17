# E5b-r1 — Kaynak kimliğine bağlı splice authorization

Önkoşul: [E5b revizyon kararı](../E5b-acceptance.md). Ortak kurallar:
[worker teslim protokolü](../../issue-05-worker-delivery-protocol.md).
Önceki kanıtlar değiştirilmedi. Canlı pilot ilan edilmedi.

## Uygulanan davranış

- Splice API'si kaynak kimliğini ayrı ve zorunlu argümanla alır:
  `replace_section_body` / `remove_section` imzalarına varsayılansız
  `expected_document_identity` eklendi. `_require_authorized` kimliği
  hedeften yeniden üretmez (tautology kaldırıldı); çağıranın taşıdığı
  değerle hedefin gerçek baytlarını karşılaştırır.
- Bütün üretim çağrı noktaları (aramayla eksiksiz: evidence 3, impact 3,
  references 4, technical 1) kimliği span yakalandığı anda
  immediate-parent belgeden bağlar; zincirli splice reparsed kimliği
  kullanır. `presentation.py` splice çağırmaz (denetlendi). Eksik
  argüman `TypeError` üretir.
- Korunanlar: `full-item-v1` aralık/profil/no-op/RNG, `span_model`
  kimliği, 3+3 etki sınırı, 0-flip matrisi, E4a parent eşlemesi, E3
  publish sınırı.

## Değişen / yeni dosyalar

- `mutations/textops.py` (imza + kapı), `mutations/operators/`
  `{evidence,impact,references,technical}.py` (11 noktada bind).
- Yeni testler (5): `tests/regression/test_span_authorization.py`
  (karşıörnek/fresh/stale/grandparent) + `test_identity_argument_is_mandatory`.
- E5a/E5b test güncellemeleri: splice çağrılarına taze kimlik argümanı.
- Belgeler: `revision-map.md`, güncellenmiş `b1-fix-contract.md`
  (E5b belgesi dondurulmuş olarak kalır).

## Test / doğrulama

- İnceleyici karşıörneği iki yolda da reddedilir (aynı bayt/konum,
  farklı kimlik); fresh çalışır; stale/grandparent reddedilir.
- Hedefli küme: **315 passed** (310 + 5 yeni). Tam offline paket:
  **404 passed** (399 + 5). Sayılar collect/run ile birebir.
  ruff check/format, mypy temiz. Sıfır canlı istek.

## Deterministik study

Yeni benzersiz kök `/tmp/sloplab-e5b-r1-OcoEUQ` (297 cases, 2
evaluators; 594 kayıt). E1e'ye göre: üç şema eki + iki devralınmış
türev + B1 etki kümesi (E5b ile bayt-aynı 6 dosya + 2 türev hash);
ortak 472 hash IDENTICAL, 0 flip, metrik katmanı aynı. Yeni paket
`complete` (485 dosya); `run-outputs.sha256` 485/485 doğrulandı. `/tmp`
kalıcı arşiv değildir.
