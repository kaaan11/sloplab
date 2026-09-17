# E5a — B1 etki envanteri (b1-impact-inventory.md)

## Yöntem ve sınırlamalar

- Kaynak: `corpus/` altındaki 60 canonical fixture, güncel parser ile
  ayrıştırıldı; her bölümde `numbered_steps` çalıştırıldı; adım satırını
  izleyen boş-olmayan, adım-eşleşmeyen satırlar devam satırı sayıldı.
- Bu liste **aday** listesidir: bir devam satırının gerçekten yetim
  kalması için planlayıcının o fixture'da `remove_reproduction_step`
  planlaması VE RNG'nin o adımı seçmesi gerekir. **Örnek/aday sayısı
  toplam etki sayısı değildir.**
- Kapsam-dışı: türetilmiş çıktılar (girdi değil), test fixture'ları,
  fence/CRLF/UTF-8 profili temiz çıktığı için korpusta varyant yok
  (aşağıda).

## Raporun üç B1 örneği (doğrulandı)

| Parent | Adım | Devam satırı |
| --- | --- | --- |
| `corpus/canonical/totiming-019/report.md:27-28` | 1 | `interleaved to cancel drift.` |
| `corpus/canonical/oauthstate-029/report.md:25-28` | 2 | `code parameter.` |
| `corpus/canonical/saml-019/report.md:26-29` | 2 | `set to another demo user, ...` |

Üçünde de bölüm `Reproduction Steps`, mekanizma güncel kodla aynıdır.

## Benzer çok satırlı öğeler (18 fixture, 20 devam satırı)

| Fixture | Bölüm | Adım | Devam satırı (kısaltılmış) |
| --- | --- | --- | --- |
| canonical-cachehdr-024 | Reproduction Steps | 3 | headers across attempts. |
| canonical-corswild-025 | Reproduction Steps | 1 | (The origin used in testing … |
| canonical-crypto-011 | Reproduction Steps | 2 | suites, recording the negotiated suite. |
| canonical-headermiss-020 | Reproduction Steps | 2 | restriction. |
| canonical-idor-004 | Reproduction Steps | 1 | `/billing/invoices/3081/download`. |
| canonical-info-006 | Reproduction Steps | 3 | the destination server log in a local test. |
| canonical-jwtalg-026 | Reproduction Steps | 2 | same symmetric secret, per the library's … |
| canonical-oauthstate-029 | Reproduction Steps | 2 | code parameter. |
| canonical-pair1b-cookie | Reproduction Steps | 1 | credentials. |
| canonical-pair4b-passpol | Reproduction Steps | 1, 3 | secret consistent …; `config/demo-auth.yaml` artifact. |
| canonical-pair8b-session | Reproduction Steps | 1, 3 | credentials.; configuration artifact. |
| canonical-ratelimit-010 | Reproduction Steps | 2 | test account over two minutes. |
| canonical-saml-019 | Reproduction Steps | 2 | set to another demo user, … |
| canonical-totiming-019 | Reproduction Steps | 1 | interleaved to cancel drift. |
| canonical-websig-018 | Reproduction Steps | 2 | header, then again with a deliberately … |
| canonical-wstoken-022 | Reproduction Steps | 3 | when the embedded token expires. |
| canonical-xsrf-003 | Reproduction Steps | 2 | form that posts new password fields … |
| canonical-xsssto-013 | Reproduction Steps | 1 | defines an image element … |

Tümü `Reproduction Steps` bölümündedir (tek liste-adımı tüketicisi
`remove_reproduction_step`); başka bölümde çok satırlı numaralı öğe yoktur.

## Profiller

- **Fence**: canonical korpusta çit yok (0). Davranış sentetik
  golden'larla sabit: ` ``` `/`~~~`/uzun işaret açar, aynı-ilk-karakter
  kapatır (uzunluktan bağımsız), karışık tür kapatmaz, kapanmamış çit
  geri kalanı yutar, çit-içi `#` başlık sayılmaz ama çit-içi adım
  eşleşir.
- **Devam paragrafı**: 20 satırın tamamı tek-paragraflık girintili
  devamdır; boş satırla bölünen ikinci paragraf yoktur.
- **UTF-8**: canonical korpusta ASCII-dışı bayt yok (0 dosya).
- **CRLF/LF**: canonical korpusta CRLF yok (0 dosya); CRLF girdide
  konumlar doğru bulunur, çıktı LF birleşir (golden'lı).

## Karakterizasyon karşılaştırması

`benchmarks/suites/v1-core.yaml` + `corpus/` güncel kodla materyalize
edildi: 474 türev dosya committed paketle bayt-eşit, suite-index gövdesi
eşit (başlıkta yalnız makine `corpus_root` farkı — E0-izinli).
`test_materialize_matches_committed_bundle` ile sabit. E5a çıktısında
açıklanmayan türev bayt farkı: **sıfır**.
