# E3b — Materialization outcomes (materialization-outcomes.md)

## Beş durum (her plan tam bir kez)

`materialize_suite`, plan döngüsünde yakalanan her planı
`materialization-ledger.jsonl` defterine plan sırasında tek satırla yazar:

| Durum | Anlam | Eski davranış |
| --- | --- | --- |
| `written` | vaka yazıldı + indekse girdi | aynı |
| `no_op` | operatör note döndü veya klon üretildi (R01 bekçisi) | `skipped` listesindeydi |
| `duplicate` | `case_id` daha önce görüldü | `skipped` listesindeydi |
| `safety_blocked` | içerik güvenliği ihlali (vaka yazılmadı) | yalnız bellek-içi listede, defterde YOKTU |
| `error` | plan adımı exception verdi (resolve/apply/safety-check/write) | tüm koşu çöküyordu |

Bir planın hatası kardeş planları durdurmaz: kayıp defterde görünür kalır.
`BaseException` (kesinti sinyalleri) yakalanmaz; plan-dışı hatalar (planlama,
dizin yazımı) eskisi gibi yükselir.

## Sayaç denklemleri

```
planned == written + no_op + duplicate + safety_blocked + error
selected_total == len(suite-index satırları) == written(mutated) + canonical_included
```

Defter başlığı (`materialization_header`) planlanan/üretilen/seçilen
sayıları birlikte taşır. `read_materialization_ledger` iç denkliği,
`check_materialization` defter↔indeks denkliğini doğrular; silinen/bozulan
satır `ValueError` verir (testle sabit). Hata detayı stabildir
(`<Tür> in <aşama>`; exception metni yok), safety detayında eşleşen ham
metin yoktur (`N violation(s) blocked`), no-op detayında operatörün sabit
notu vardır.

## Ortak study koordinasyonu (izolasyon)

`scoring/harness.py` iki katman sunar:

- `run_suite` (katı, değişmedi): her exception yayılır.
- `run_suite_with_outcomes` (E3b): yalnız tipli operasyonel
  `EvaluationFailure` vaka outcome'una izole edilir
  (`CaseOutcome{status=failed, record=None, failure=...}` — puanlanan kayıt
  yok, uydurma karar yok);
  `records + failed == cases`. Beklenmeyen program/config hatası
  sarılmadan yükselir.

Bağlantı: `run_deterministic_study` başarısızlıkları koşuya özel
`outcomes.jsonl` dosyasına yazar (**yalnız başarısızlık varsa**; başarılar
`records.jsonl`'da kalır — uzlaşma: `records + failed == planned`).
CLI `evaluate`/`benchmark` aynı mekanizmayla devam eder ve her izole
başarısızlığı `FAILED-EVAL (<tür>)` satırıyla görünür kılar (stderr).
Pilot ledger'ı (E2) değişmedi.

## Görünür kayıp yolları

- Kesinti (plan hatası): `error` satırı + koşu tamamlanır (indeks/defter
  kısmi nüfusla yayımlanır).
- Duplicate: ilk yazan kazanır, tekrar `duplicate` satırı olur.
- Safety-blocked: vaka yazılmaz, indeks dışı kalır, defter + CLI özeti
  (`SAFETY:` satırları, materialize komutu çıkış 1) kaybı gösterir.
- Study koşucusu safety kaybında durmaz; kayıp defterde ve pakette kalır
  (davranış değişmedi, görünürlük eklendi).
