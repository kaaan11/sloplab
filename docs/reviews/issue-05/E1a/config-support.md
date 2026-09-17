# E1a — Config destek matrisi

## Desteklenen (davranış korunur)

| Alan | Değer | Not |
| --- | --- | --- |
| `evaluators[*].config` | `{}` (boş) | Hash'lenir ama uygulanmaz; E1a değiştirmez |
| `evaluators[*].name` | Kayıtlı ad (`oracle`, `rules-baseline`, `evidence-graph-baseline`) | Registry'den çözülür; hard-code yok |
| `analysis.paired_comparison` | `true` | CLI analizinde kullanılır |
| `analysis.error_taxonomy` | `true` | CLI analizinde kullanılır |
| `analysis.bootstrap_resamples` | Şema aralığı (`>=100`), örn. 500 | CLI bootstrap'ına aynen aktarılır |
| `analysis.bootstrap_ci` | Şema aralığı (`0..1` açık), örn. 0.99 | Aynı şekilde aktarılır |
| `provenance.record_*` (3 alan) | `true` | Manifestoya yazılır |
| `base_seed` / suite `base_seed` | Eşit veya farklı | Generation seed suite'ten, analysis seed study'den gelir (değişmedi) |

## Reddedilen (yan etkiden önce `StudyConfigError` / CLI `Error:`)

| Alan | Ret koşulu | Hata adı |
| --- | --- | --- |
| `evaluators[i].config` | nonempty mapping | evaluator adı + `evaluators[i].config` (değerler yazılmaz) |
| `evaluators[i].name` | kayıtlı değil | ad + registry listesi (`unknown evaluator ...`) |
| `analysis.paired_comparison` | `false` | alan adı (uygulanmadığı için) |
| `analysis.error_taxonomy` | `false` | alan adı (uygulanmadığı için) |
| `provenance.record_commit_sha` | `false` | alan adı |
| `provenance.record_suite_hash` | `false` | alan adı |
| `provenance.record_evaluator_config_hash` | `false` | alan adı |

## Seed rollerinin mevcut anlamı (değişmedi)

- Suite `base_seed` (`benchmarks/suites/v1-core.yaml:8`): mutasyon tohumu ve tahsis
  (`materialize_suite` yolu).
- Study `base_seed` (`experiments/configs/deterministic-study-v0.2.yaml:19`):
  manifesto kaydı + bootstrap yeniden örnekleme tohumu (CLI).
- İkisi bugün `20260825` ile eşit; farklı olmaları bu pakette ret üretmez. Açık
  kimliklendirme (hangi seed nereye) E1'in sonraki paketine kaldı.

## E1'e kalan işler (bu pakette dokunulmadı)

StudySpec/CaseSnapshot mimarisi, prompt kimliği, yeni hash şeması, LLM outcome/bütçe,
metrik düzeltmesi, kaynak düzenlemesi, bundle atomikliği, bilimsel yöntem seçimi,
framework/registry-factory/evaluator özelliği.
