# E3b — Legacy okuyucu sözleşmesi (legacy-reader-contract.md)

## Sınır: tek kapı, iki mod

Bütün sonuç-paketi okumaları `experiments/bundle.py:open_result_dir`
üzerinden geçer (CLI `compare`, CLI `report`, benchmark/STUDY iç
okumaları, `llm_bench` tüketimi). Kapı iki mod döndürür:

- `"complete"`: işaret var ve strict doğrulama geçti — yeni şema
  garantileriyle oku.
- `"legacy"`: işaretsiz ama legacy biçimli (`manifest.json`,
  `records.jsonl`, `outcomes.jsonl`, `run.jsonl`, `suite-index.jsonl`
  izlerinden biri var) — **açık legacy modda** oku: garanti yok,
  dönüştürme yok, tarihsel dosya asla yeniden yazılmaz.

İşaretli-ama-bozuk ve tanınmayan dizinler `BundleError` ile reddedilir;
sessiz geçiş yoktur (bypass regression testleri:
`test_reader_boundary.py` — davranışsal redler + casusla bağlantı kanıtı).

## Tüketici kuralları

| Okuyucu | complete | legacy | bozuk/tanınmayan |
| --- | --- | --- | --- |
| CLI `compare` | doğrula, oku | `note:` ile oku (stderr) | `ClickException` |
| CLI `report` | doğrula, oku | `note:` ile oku (stderr) | `ClickException` |
| benchmark iç okuma | (kendi çıktısı; legacy) oku | oku | `ClickException` |
| study iç okuma | — (işaret daha yazılmadı) | oku | `ClickException` |
| `llm_bench` pilot tüketimi | `verify_bundle` geçmezse çıkış 1 (kontrollü yayın) | — (pilot her zaman işaretli yazar) | çıkış 1 |

Legacy notu stderr'e yazılır; stdout tabloları makinece okunabilir kalır.

## Legacy tanıma (dönüştürmeden)

- `benchmarks/results/v1-core-example` (committed `run.jsonl` paketi):
  `legacy`; strict reader reddeder.
- E3a-öncesi `/tmp` study koşuları (`manifest.json` + `records.jsonl`,
  işaretsiz): `legacy`; strict reader reddeder.
- Ara çıktı (işaretsiz yeni üretim, örn. doğrudan koşucu çıktısı):
  `legacy` biçimli görünür ve eşit şekilde reddedilir.
- Ayrıntılı legacy tüketimi (alan eşleme, migrate): bu paketde yok;
  legacy okuma tarihsel baytları olduğu gibi tüketir.

## Analiz önbelleği notu

Kodda yazmalı analiz önbelleği yoktur: `analysis.json` her study koşusunda
yeniden hesaplanır. Önbellek rolündeki okumalar (committed metrikler,
referans paketler) yukarıdaki aynı kapıdan geçer: CLI `compare` metrik
dizinlerini, dondurulmuş E0 yardımcısı kendi politikasıyla okur
(değiştirilmedi).

## bundle_complete / coverage_sufficient ayrımı

Teknik tamamlanma (`completion.json` doğrulaması) ile bilimsel coverage
yeterliliği ayrı alanlardır ve birbirine eşitlenmez:

- Pilot manifestosu ikisini de taşır: `"bundle_complete": true` (bütün
  paket dosyaları işaretle yayımlandı) ve `"coverage_sufficient":
  <full_coverage>` (planlanan her vaka × repeat başarılı). Kısmi başarıda
  ilki `true`, ikincisi `false` kalır (testle sabit).
- Study politikası: planlanan her değerlendirme puanlandı
  (`outcomes.jsonl` yoksa ya da yalnız başarı satırları içeriyorsa
  yeterli). Study manifestosu bayt-kararlılığı için değişmedi.
- Alt akış (E4) yeterliliği `coverage_sufficient` (veya study kuralı)
  üzerinden okur; teknik işareti bilimsel onay diye kullanmaz.
