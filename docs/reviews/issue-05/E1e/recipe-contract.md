# E1e — Çözülmüş deney tarifi sözleşmesi (recipe-contract.md)

Bu belge uygulamadan önce yazıldı; uygulama ve testler aynen bunu takip eder.
Rutin isim tercihleri için onay istenmedi; genel mimariye büyütülmedi.

## Dosya: execution-recipe.json (`schema_version: 1`)

Başarılı deterministik study çıktısına eklenir. `records.jsonl`, `analysis.json`,
`manifest.json`, `input-identity.json` şemaları değişmez.

```json
{
  "schema_version": 1,
  "generation": {
    "base_seed": 20260825,
    "include_canonical_cases": true,
    "policies": {"valid": {"variants_per_fixture": 8, "operators": ["..."]}},
    "suite_name": "v1-core"
  },
  "generation_hash": "<64-hex>",
  "evaluation": {"evaluators": [{"name": "rules-baseline", "version": "0.1.0", "config": {}}]},
  "evaluation_hash": "<64-hex>",
  "analysis": {
    "bootstrap_seed": 20260825,
    "bootstrap_resamples": 2000,
    "bootstrap_ci": 0.95,
    "paired_comparison": true,
    "error_taxonomy": true
  },
  "analysis_hash": "<64-hex>",
  "settings_hash": "<64-hex>",
  "inputs_hash": "<64-hex>",
  "selection_hash": "<64-hex>",
  "execution_hash": "<64-hex>",
  "locations": {"suite_config_path": "/abs/path/suite.yaml", "corpus_root": "/abs/path/corpus"},
  "metadata": {
    "head": "abc123...|null",
    "dirty": true,
    "python_implementation": "CPython",
    "python_version": "3.13.15",
    "sloplab_version": "0.2.2",
    "uv_lock_sha256": "<64-hex>|null"
  }
}
```

## Bölümler ve hash girdileri

Hash nesneleri `domain: "sloplab.recipe"`, açık `type` ve `version: 1` zarfı taşır;
E1d JSON encoding kuralı kullanılır (`sort_keys`, açık separator, UTF-8,
`ensure_ascii=False`, `allow_nan=False`). Dict anahtar sırası etkisizdir.

- `generation` (uygulanan üretim girdileri; sıra değiştirilmez, operator listeleri
  dizidir ve sırası etkilidir): `{base_seed (suite generation seed),
  include_canonical_cases, policies: {grup: {variants_per_fixture, operators[]}},
  suite_name}` → `generation_hash`. `corpus_root`/path içermez.
- `evaluation` (çözümlenmiş nesneler; sıra korunur): `{evaluators: [{name, version,
  config}]}` → `evaluation_hash`. İsim/version gerçek nesneden; config kabul
  edilmiş boş kopya.
- `analysis` (**uygulanan seçenekler**, bilimsel geçerlilik değil):
  `{bootstrap_seed (= study.base_seed), bootstrap_resamples, bootstrap_ci,
  paired_comparison, error_taxonomy}` → `analysis_hash`. Study seed ve generation
  seed ayrı isimlerle taşınır; farklı olmaları hata değildir, üretimi değiştirmez.
- `settings_hash`: `{generation_hash, evaluation_hash, analysis_hash}` bağı.
- `inputs_hash` + `selection_hash`: aynı in-memory identity nesnesinden kopyalanır
  (sonradan dosya okunarak yeniden üretilmez).
- `execution_hash`: `{inputs_hash, selection_hash, settings_hash}` bağı.

## Hash dışı alanlar

- `locations`: çözümlenmiş mutlak `suite_config_path` + `corpus_root`. İçerik
  kimliği (`generation_hash`) ile uygulanan root ayrı taşınır; aynı
  metin/etiket/politika/ayar farklı kökte aynı semantik hash'leri verir.
- `metadata` (kod/ortam, `settings_hash`'e karışmaz): mevcut HEAD, dirty göstergesi
  (dirty HEAD tam kod kimliği değildir), Python implementation/version, paket
  versiyonu, varsa lock SHA-256. Shell/ortam dökümü ve credential yok. Mevcut
  version alanları değişmez.

## Çözümleme sınırı (davranış)

Mevcut preflight → yol çözümü → suite yüklemesi bir sınırda tamamlanır; tarif
burada dondurulur: suite nesnesi (aynı nesne materializer'a verilir, dosya tekrar
okunmaz), çözümlenmiş evaluator nesneleri (çalışma döngüsü registry'ye tekrar
sormaz; thread/process güvenliği iddia edilmez), repeat_index + provenance
seçenekleri. CLI analizine gerek duyulan bootstrap ayarları bu kopyadan gelir;
orijinal config'e dönülmez. API analiz üretmez ve ürettiği iddia edilmez (tarifte
tamamlanma iddiası alanı yoktur).
