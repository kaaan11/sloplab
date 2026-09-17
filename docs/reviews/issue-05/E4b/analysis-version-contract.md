# E4b — Analiz sürüm sözleşmesi (analysis-version-contract.md)

## Sürümlü yayın

Study, `analysis.json` yanına ayrı adla sürümlü analiz yazar:
`analysis-vN.json` (`N = ANALYSIS_DEFINITION_VERSION`, bugün `1`).
Tarihsel `analysis.json` ne üzerine yazılır ne değiştirilir; biçimi ve
üretimi aynen korunur.

Sürüm belgesi türü, kaynak kayıt kümesinin hash'i, selection/outcome
coverage'ı ve analiz tanım sürümüyle ayrışamaz; birlikte taşınır:

- `analysis_schema` (zarf) + `analysis_version` (tanım: metrik kümesi,
  formüller, uygunluk kuralları),
- `records_path` + `records_sha256` (tüketilen dosyanın tam bayt hash'i)
  + `records_count`,
- `coverage`: evaluator başına `{scored, failed}`,
- `bundles`: doğrulanan metrik paketleri (coverage dahil),
- tanımlayıcı not: betimsel case-weighted; estimand/ağırlık/aralık
  iddiası yok.

Tanım değişen her formül/uygunluk revizyonu sürümü artırır. Okuyucu yalnız
güncel sürümü kabul eder; eski/yabancı sürüm yeniden hesaplamaya
yönlendirilir (sessiz çapraz-sürüm okuma yok). Yeni nihai bilimsel tercih
(estimand/CI), kullanıcı ayrıca kararlaştırmadıkça ilan edilmez.

## Tüketici kapısı (`read_versioned_analysis`)

Sırayla: ayrıştırma → bilinen zarf/tanım sürümü → paket `complete`
doğrulaması (strict reader) → bağlı records dosyası mevcut ve hash eşleşir
→ satır sayısı eşleşir → evaluator başına scored sayıları gömülü coverage
ile eşleşir. İlk ihlal `AnalysisError` yükseltir:

- **stale cache** (yayın sonrası değişen records): hash/satır uyuşmazlığı;
- **karışık analiz** (başka run'un analizi/ kayıtları): hash uyuşmazlığı;
- **coverage uyuşmazlığı**: scored sayıları tutmaz;
- **sürüm değişimi**: desteklenmeyen tanım → yeniden hesapla.

CLI `study` sürümlü yayını üretir; CLI `compare` (dizinde tek
`analysis-v*.json` varsa; çoksa açık hata) ve CLI `report --analysis`
aynı doğrulanmış belgeyi tüketir — yeniden türetme yok, kayma yok.
Legacy girdiler eski yoldan, açık notla okunmaya devam eder.
