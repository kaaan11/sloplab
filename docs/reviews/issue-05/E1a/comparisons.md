# E1a — E0/yeni çalışma karşılaştırması

Yeni koşu: `/tmp/sloplab-e1a-ppqPYl/run` (E1a koduyla, 297 vaka, 2 evaluator).
Referans: `/tmp/sloplab-e0-zVHDyy/run-a` (E0, aynı config, aynı kök).
Yöntem: E0 rev3 `helpers/compare_e0.py` read-only çağrısı
(`run-a`, `yeni-run`, `run-a`) — allowlist genişletilmedi.
Günlük: `/tmp/sloplab-e1a-ppqPYl/logs/compare-e0.stdout.log` (exit 0, `RESULT: OK`).

## Sonuç

| Küme | A/B bölümü (run-a vs yeni-run) | Hüküm |
| --- | --- | --- |
| Dosya kümesi | 480 / 480 IDENTICAL | yeni/eksik dosya yok |
| Ham hash (478 dosya) | IDENTICAL | records, derived dosyalar, analysis, rapor, CSV dahil |
| `suite-index.jsonl` | ham bayt IDENTICAL | aynı kök → aynı mutlak korpus yolu |
| `manifest.json` | yalnız `started_at`, `finished_at` farklı | açıklanan zaman alanları |

## Sayılar

- Vaka: 297 (60 canonical + 237 derived); evaluator kayıt satırı: 594 (evaluator başına 297).
- Karar, hedef, vaka sayısı, metrik farkı: yok (records/analysis ham eşit).
- Yeni çıktı hash envanteri: `/tmp/sloplab-e1a-ppqPYl/logs/run-outputs.sha256` (480 dosya).

Bu paket farklı bir bilimsel analiz sürümü değildir; E1a kabulü için beklenen
"fark yok" sonucu alındı. Golden dosya güncellenmedi.
