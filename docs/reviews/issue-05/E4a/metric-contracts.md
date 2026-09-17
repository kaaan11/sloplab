# E4a — Metrik sözleşmeleri (metric-contracts.md)

Bütün agregalar **case-weighted betimsel** sonuçlardır (her kayıt/çift bir
oy; parentlar child sayısınca ağırlanır); isim böyle anılır. Estimand
seçimi, parent-eşit ağırlık, bootstrap bağımsızlığı ve authored boyut
hedefleri bu pakette seçilmez. Yeni CI yöntemi yoktur.

## Kayıt sözleşmesi (reader sınırı: `validate_metric_records`)

`compute_metrics` her çağrıda doğrular; ihlal `ValueError` ile yükselir,
asla sessiz düzeltilmez:

- **Tekillik**: `(case_id, evaluator_name, repeat_index)` anahtarı tektir.
- **`correct` uyumu**: saklanan bayrak yeniden hesaplanan karara eşittir.
- **Failed/not_run girmez**: `failed=True` işaretli legacy satırlar
  puanlanmaz (üst akışta `raise_if_failed_result` ile çevrilir); outcome
  defterlerindeki failed/not_run satırları doğruluk, ECE veya karar
  birliğine (paired/stability girdileri) taşınmaz.
- **Parent/operator bağları**: mutated satırda ikisi de doludur. Ebeveyn
  satırının aynı girdide bulunması metrik başına çözümlenir (aşağıda);
  filtrelenmiş alt kümeler bu yüzden reddedilmez.
- Beklentisiz (`expected=None`) satırlar puanlanmaz ama sayılır
  (`unscored_no_expectation`).

## Metrik sözleşmeleri

| Metrik | Analiz birimi | Pay / payda | Eksik veri | Sıfır payda |
| --- | --- | --- | --- | --- |
| decision_accuracy | scored kayıt | correct / scored | beklentisiz sayılır | scored=0 → `0.0` (bildirilen kural) |
| false_reassurance | non-accept-expected kayıt | accept / eligible | — | tanımsız + neden |
| over_rejection | accept-expected kayıt | reject / eligible | — | tanımsız + neden |
| mutation_detection | degrading mutated kayıt | detected / eligible | — | tanımsız + neden |
| robustness_delta | ebeveynle eşleşen nötr çift | drift / çift | ebeveynsiz çift sayılır | tanımsız + neden |
| presentation_susceptibility | eşleşen presentation çifti | Σ(child−parent) / çift | çözümsüz çift sayılır | tanımsız + neden |
| calibration_error | [0,1] gözlemi | Σ w·\|conf−acc\| | aralık-dışı sayılır | tanımsız + neden |
| dimension_mae | beklentili boyut | \|mae\| / boyut | beklentisiz sayılır | tanımsız + neden |

- **Susceptibility (E4a düzeltmesi)**: çift başına `child_accept −
  parent_accept` ortalaması. Her çift anlaşıyorsa sonuç tam `0` (çocuk
  dağılımı ne olursa olsun). Ebeveyn bağı yoksa (ebeveyn satırı yok veya
  accept-expected ebeveyn) çift çözülmez; hiç çift yoksa metrik
  `"no presentation-mutated cases with resolvable non-accept parents"`
  nedeniyle tanımsızdır.
- **ECE (E4a düzeltmesi)**: son bin her zaman sağdan kapalıdır; `1.0`
  bin arkadaşlarıyla birlikte sayılır; her aralık-içi kayıt tam bir bine
  girer (`binned == observations`, testle sabit). Aralık-dışı/NaN
  `out_of_range_excluded` olarak sayılır.
- Sıfır-payda kuralı: oran tanımsızsa değer `None` + `undefined_reason`
  (tek istisna: boş kümede `decision_accuracy == 0.0`, bildirilen kural).
- Her metrik `metric_coverage` altında `{eligible/pairs/observations…,
  excluded/missing…, undefined_reason}` taşır; uygunsuz veri paydadan
  sessizce kaybolmaz.

## Karşıörnekler: eski / yeni sonuç tablosu

| Karşıörnek | Eski (hatalı) | Yeni (sözleşme) |
| --- | --- | --- |
| Eşit çiftler (1 accept-çifti + 3 reject-çifti) | `-0.25` | `0.0` |
| `0.95/doğru` + `1.0/yanlış` ECE | `0.025` | `0.475` |
| Ebeveynsiz presentation çocuğu | `None` (nedensiz) | `None` + `"...resolvable non-accept parents"` |
| Üretim verisi (rules-baseline susc.) | `-0.0189` | `0.0` |
| Üretim verisi (evidence-graph susc.) | `0.0068` | `0.0` |
| Üretim verisi ECE/drift/accuracy | aynı | aynı (değişmedi) |

Başarı yolundaki ham kararlar/hedefler değişmedi (`records.jsonl`,
`suite-index.jsonl`, manifesto kimlik alanları bayt-eşit). Değişen
türevler yalnız `analysis.json` (düzeltilmiş susceptibility + yeni
`metric_coverage` anahtarı) ve `report.md` (işlenmiş değerler).
