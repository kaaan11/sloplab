# E1d — input-identity.json şema sözleşmesi

## Dosya

Ad: `input-identity.json` (başarılı deterministik study çıktısında).
Üst düzey: `schema_version` (sabit `1`), `cases` (çalışma sırasına göre vaka satırları,
vaka başına bir satır — evaluator sayısı kadar çoğaltılmaz), `selection_hash`,
`inputs_hash`.

## Vaka satırı

Mevcut alanlar aynen: `case_id`, `case_kind`, `parent_id`, `operator`, `report_class`,
`seed`. Ek kimlikler: `report_hash`, `target_hash`, `input_hash`.

## Hash nesneleri (hepsi domain/type + version içerir)

- `report`: `{"domain": "sloplab.input", "type": "report", "version": 1, "text": raw_text}`
  → `report_hash`. Snapshot `raw_text`'in kimliğidir; **disk dosyasının ham hash'i
  değildir**. Parser satır sonunu normalize etmişse bu disk bayt eşitliği diye
  sunulmaz. Render edilmiş LLM prompt hash'iyle karıştırılmaz.
- `target`: `{"domain": "sloplab.input", "type": "target", "version": 1,
  "expected_decision": <string|null>, "expected_dimensions": {<dim>: <float>}}`
  → `target_hash`. `None` ile karar string'i ayrıdır (null vs string). Eksik boyut
  ile açık `0.5` ayrıdır (yok anahtar vs değer); hedef dict'i kopyalanarak
  sabitlenir. NaN/Infinity `allow_nan=False` ile anlaşılır hataya düşer.
- `input`: `{"domain": "sloplab.input", "type": "input", "version": 1,
  "report_hash": ..., "target_hash": ...}` → `input_hash`.
- `selection`: `{"domain": "sloplab.input", "type": "selection", "version": 1,
  "case_ids": [...]}` → `selection_hash`.
- `inputs`: `{"domain": "sloplab.input", "type": "inputs", "version": 1,
  "inputs": [...]}` → `inputs_hash`.

Farklı nesne türleri aynı kimlik alanına çakışamaz (envelope ayrımı).

## Serializer sözleşmesi

JSON hash nesnelerinde: `sort_keys=True`, açık `separators=(",", ":")`, UTF-8,
`ensure_ascii=False`, `allow_nan=False`. Dosya aynı canonical baytlarla + `\n` ile yazılır.
Bu, bütün diller/gelecek Python sürümleri için standart canonical JSON garantisi
**değildir**. Kimlik karşılaştırması desteklenen şema/sürümle (`schema_version: 1`)
sınırlıdır.

## Sıra ve kapsam kuralları

- Dict anahtar sırası hash'i etkilemez; **vaka sırası etkiler** (selection/inputs).
- Dahil edilmeyenler: mutlak corpus/out dizini, `ReportDocument.path`, timestamp,
  run_id, git HEAD, evaluator adı/versiyonu, karar çıktısı. İki evaluator aynı girdide
  farklı evaluator kimlikleri yüzünden engellenmez. Kaynak kodu/ortam kimliği sonraki
  recipe paketidir.
