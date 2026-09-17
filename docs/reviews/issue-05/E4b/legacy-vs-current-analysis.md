# E4b — Legacy ve güncel analiz (legacy-vs-current-analysis.md)

Yöntem: tarihsel kabul referansının (`/tmp/sloplab-e1e-review-hoxabV/run`,
594 kayıt) ham kayıtları güncel kodla bağımsız yeniden hesaplandı;
legacy değerler referans `analysis.json` eserinden okundu. Kalıcı test
(`test_historical_recomputation.py`) aynı karşılaştırmayı committed
`benchmarks/results/v1-core-example` paketi üzerinde tekrar üretir.

## Metrik bazı fark/neden tablosu (E1e referansı)

| Evaluator | Metrik | Legacy | Güncel | Neden |
| --- | --- | --- | --- | --- |
| rules-baseline | presentation_susceptibility | `-0.0189` | `0.0` | paired fix (E4a): dengesiz çiftler |
| evidence-graph-baseline | presentation_susceptibility | `0.0068` | `0.0` | paired fix (E4a): dengesiz çiftler |
| evidence-graph-baseline | robustness_score | `0.4465` | `0.4472` | paired fix'in türev etkisi (`1−susc` terimi) |
| ikisi de | calibration_error | aynı | aynı | değişmedi (kenar güven yok) |
| ikisi de | decision_accuracy + 12 metrik | aynı | aynı | değişmedi |
| ikisi de | metric_coverage | yok | var | coverage zarfı eklendi (E4a) |

Committed örnekte tablo daha dardır: yalnız rules susceptibility
(`-0.0189 → 0.0`) ve coverage zarfı farklıdır; oracle dahil gerisi aynıdır
(testle sabit).

## Okuma kılavuzu

- Ham karar/hedef kayıtları (`records.jsonl`) bayt-eşit: farklar yalnız
  düzeltilmiş türevlerdedir.
- Eşit çift kümelerinde susceptibility `0.0` olması formülün doğruluğudur;
  sıfırın kendisi kalite hükmü değildir (aşağıdaki uygunluk belgesine bak).
- `robustness_score` yardımcı özetidir; bileşen değişimlerini aynen yansıtır.
