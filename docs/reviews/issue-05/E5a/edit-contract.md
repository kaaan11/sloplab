# E5a — Düzenleme sözleşmesi (edit-contract.md)

Kapsam: parser (`corpus/parser.py`), `models/report.py`,
`mutations/textops.py`, liste adımı kullanan operatörler
(`remove_reproduction_step`; `step_lines`/`numbered_steps` okuyucuları:
rules `baseline`/`evidence_graph`), materializer, test fixture'ları.
Bu paket davranışı DÜZELTMEZ: aşağıdaki önkoşullar makinece
doğrulanabilir sözleşme + testlerdir; operatör-içi zorlama E5b'nindir.

## Yetkili kaynak aralığı

Bir `ReportSection` aralığı, şu üçü birlikte sağlanıyorsa belgenin
yetkili aralığıdır (`textops.span_authorized`):

1. `1 <= start_line <= end_line <= len(belge satırları)`;
2. ham satırlar `[start−1 : end]` birleşiminin `\n` kırpılmış hali
   `section.text` ile bayt-eşit;
3. başlıklı bölümde ilk satır ATX başlığı olarak ayrışır ve metin +
   seviye eşleşir; başlıksız bölüm yalnız 1. satırda başlar.

Belge kimliği etiketler (`fixture_id`, `path`) değil içerik hash'idir
(`textops.document_identity` = SHA-256(raw_text)); etiketler taşınabilir,
kimlik baytlara bağlıdır.

## Tek adımlı parent sınırı

Operatörler her uygulamada aralığı **doğrudan parent belgeden** taze
çözer (single step); üst-parent zinciri kurulmaz, zincirleme eklenmez.
İkinci nesil düzenleme, çocuğun kendi metnini yeniden ayrıştırır.
Büyükanne aralığı çocuk belgede `span_authorized` testini geçemez
(kaymış satırlar) — testle sabit.

## Kontrollü ret / no-op tablosu

| Durum | Davranış (güncel, sabitlenmiştir) |
| --- | --- |
| Bayat aralık (değişmiş belgede eski konum) | `span_authorized` → `False` (E5a); operatörler henüz sormaz (E5b zorlar) |
| Belirsiz syntax (çit-içi `#`/adım, kapanmamış çit, karışık çit türü) | Parser çit-içi başlığı yoksayar ama çit-içi adımı eşleştirir; kapanmamış çit geri kalanı yutar; karışık tür kapatmaz — hepsi golden testlidir, kısıt olarak belgelenir |
| Yanlış parent (eşleşen bölüm yok) | `{"note": ...}` ile no-op, girdi aynen döner (mevcut) |
| CRLF girdi | Konumlar doğru; çıktı LF birleşir (bayt değişimi belgeli) |
| UTF-8 | Değiştirme/silme yollarından aynen geçer |

## Bilinen B1 mekanizması (düzeltilmedi)

`numbered_steps` satır-bazlıdır: çok satırlı adım yalnız ilk satırıyla
temsil edilir. `RemoveReproductionStep` tek-adım modunda o satırı düşürür;
devam satırları yetim kalır (totiming-019: `interleaved to cancel drift.`
tek başına). Bölüm metni 0. satırda başlığı taşır; operatör gövdeyi
kurarken başlığı düşürür (`offset != 0`), `replace_section_body`
önekten geri koyar.
