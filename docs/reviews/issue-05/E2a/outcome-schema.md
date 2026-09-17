# E2a — Outcome şeması (outcome-schema.md)

## outcomes.jsonl

Pilot çıktı dizininde, satır başına bir plan sonucu (JSON Lines).
Sıra: repeat ana döngü, içinde seçili vaka sırası. Tekil anahtar:
`(case_id, evaluator_name, repeat_index)`.

```json
{"schema_version": 1, "status": "success", "case_id": "canonical-x-001",
 "evaluator_name": "llm-json", "repeat_index": 0,
 "record_ref": {"case_id": "canonical-x-001", "repeat_index": 0}}
{"schema_version": 1, "status": "failed", "case_id": "canonical-x-002",
 "evaluator_name": "llm-json", "repeat_index": 0,
 "error_kind": "timeout", "adapter_attempts": 3,
 "rendered_prompt_hash": "<64-hex>", "detail": "TimeoutError: simulated timeout"}
{"schema_version": 1, "status": "not_run", "case_id": "canonical-x-002",
 "evaluator_name": "llm-json", "repeat_index": 1, "reason": "budget_exhausted"}
```

- `success`: kararı `records.jsonl`'deki `CaseRecord` taşır; satır yalnız
  `record_ref` ile bağlanır.
- `failed`: `error_kind` ∈ {parse, timeout, transport, budget, legacy};
  `adapter_attempts` mantıksal adapter deneme sayısıdır (fiziksel gönderim sayısı
  değildir; fiziksel sayaçlar manifestodaki client sayaçlarıdır).
  `rendered_prompt_hash` gönderilen prompt metninin UTF-8 SHA-256'sıdır (bilinmiyorsa
  boş string). `detail` sabit, kontrollü bir hata kodudur; ham cevap/prompt/credential/
  exception metni/yığın dökümü taşımaz. **Karar alanı
  (`decision`/`confidence`/`dimensions`) yoktur.**
- `not_run`: bütçe nedeniyle başlamayan plan; `reason` açık nedendir
  (`budget_exhausted`). Bu fazda başka not_run nedeni üretilmez.

## records.jsonl (pilot)

Yalnız başarı `CaseRecord` satırları. Tümü başarısızken dosya boş (0 bayt) olur;
bu, boş defterle birlikte geçerli teknik sonuçtur — başarılı ölçüm veya
tamamlanmış benchmark sayılmaz.

## Manifesto ek alanları

`planned`, `successful`, `failed`, `not_run`, `scored`;
`planned = successful + failed + not_run`, `scored = successful`.
`stability` tam başarı kapsamındaysa hesaplanır, yoksa `{}` +
`stability_omitted_reason` (`incomplete-success-coverage` /
`single-repeat-or-empty`). `request/error/timeout` fiziksel client sayaçlarıdır.

## EvaluationFailure (typed)

`error_kind`, `adapter_attempts ≥ 1`, `rendered_prompt_hash`, `detail` taşıyan
frozen exception; karar/confidence/dimensions alanı yoktur. Legacy
`metadata.failed=True` sonucu sınırda `error_kind: legacy` failure'a çevrilir
(denenen tek gözlem çağrısı `adapter_attempts: 1`; hash varsa korunur).
Beklenmeyen program hataları ve config hataları failure'a çevrilmez, aynen yükselir.
Ledger atomikliği E3 garantisi değildir.

## Etiket yetkisi

`evaluator_requires_labels(evaluator) -> bool` (default False). Yalnız `True`
bildiren (oracle) ground-truth kopyası alır; diğerleri boş mapping görür (her
çağrıda yeni kopya). Pilot LLM context'i boş labels taşır; pilot kayıtlarının
ground-truth alanları (`expected_decision` vb.) korunur. Bu veri minimizasyonudur;
in-process kasıtlı erişimi engelleyen sandbox değildir.
