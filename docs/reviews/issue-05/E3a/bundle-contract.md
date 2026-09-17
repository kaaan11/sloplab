# E3a — Bundle sözleşmesi (bundle-contract.md)

## Yeni şema (strict yol)

Sonuç paketleri iki türdür: `study` (CLI `study` çıktısı) ve `llm-pilot`
(`run_llm_pilot` çıktısı). Her yeni-şema paket dizini, **en son**
yayımlanan `completion.json` işaretini taşır:

```json
{"bundle_schema": 1, "kind": "study", "files": {"<relpath>": "<sha256>", ...}}
```

- İşaret, kendisi hariç dizindeki **bütün** dosyaların SHA-256'sını taşır
  (study'de `adversarial/` ağaçları dahil). Gerekli dosya kümesi ve
  hash'ler tamamlanmadan çalışma tamamlanmış görünmez.
- Belge deterministiktir (sıralı anahtarlar, zaman damgası yok); çalışmaları
  arası bayt-eşitliği kontrollerini bozmaz (işaretin varlığı hariç).
- Tür asgari dosyaları (`src/sloplab/experiments/bundle.py`,
  `KIND_REQUIRED_FILES`):
  - study: `manifest.json`, `records.jsonl`, `suite-index.jsonl`,
    `input-identity.json`, `execution-recipe.json`, `analysis.json`
    (ayrıca `report.md`, `results.csv` ve materyalize ağaçlar harita
    üzerinden kapsanır);
  - llm-pilot: `manifest.json`, `records.jsonl`, `outcomes.jsonl`.

## Strict reader

`verify_bundle(dizin, kind=...)` sırayla ister: işaret varlığı +
ayrıştırılabilirlik + bilinen şema/tür; bildirilen tür eşitliği; türün
asgari dosyaları; **bire bir dosya kümesi** (eksik yok, listede olmayan
fazlalık yok); listedeki her dosyada hash eşitliği. İlk ihlalde
`BundleError` yükselir. Başarılı publish bütün iç hash'lerle açılır
(dönen belge).

`classify_bundle(dizin)` tüketmeden tanır: `"complete"` (işaretli ve
doğrulanan), `"incomplete"` (işaretli ama bozuk, ya da tanınmayan),
`"legacy"` (işaretsiz ama legacy biçimli). İşaretsiz kesintiye uğramış yeni
yayın da legacy biçimli görünür ve strict reader tarafından eşit şekilde
reddedilir; otomatik dönüştürme yoktur (ayrıntılı legacy tüketimi E3b).

## Yayın sınırı ve staging varsayımı

Yazarlar dizine doğrudan yazar; işaret **son** yazılır
(pilot: manifest sonrası; study: rapor sonrası — casus testiyle sabit).
Dosyalar arası çöküş, işaretsiz veya hash'i tutmayan dizin bırakır; strict
reader reddeder. Aynı filesystem içindeki rename işlemi dosya başına
atomiktir; bütün-bundle atomikliği diye sunulmaz — garanti işarettedir,
sıralamada değil.

Okuyucu, işaret yokken yeni paketi kabul etmez. Eski artefaktlar
değiştirilmez. Metrik yeniden hesabı E4, materialization durum defteri ve
legacy tüketimi E3b kapsamıdır.
