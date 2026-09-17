# E1b — E0/yeni çalışma karşılaştırması

Yeni koşu: `/tmp/sloplab-e1b-ihv1hN/run` (E1b koduyla, 297 vaka, 2 evaluator).
Referans: `/tmp/sloplab-e0-zVHDyy/run-a` (E0, aynı config, aynı kök; mevcut).
Yöntem: E0 rev3 `helpers/compare_e0.py` read-only çağrısı
(`run-a`, `yeni-run`, `run-a`) — allowlist genişletilmedi.
Günlük: `logs/compare-e0.stdout.log` (exit 0, `RESULT: OK`; stderr boş).

## Sonuç

| Küme | run-a vs yeni-run | Hüküm |
| --- | --- | --- |
| Dosya kümesi | 480 / 480 IDENTICAL | yeni/eksik dosya yok |
| Ham hash (478 dosya) | IDENTICAL | records, derived dosyalar, analysis, rapor, CSV dahil |
| `suite-index.jsonl` | ham bayt IDENTICAL | aynı kök → aynı mutlak korpus yolu |
| `manifest.json` | yalnız `started_at`, `finished_at` farklı | açıklanan zaman alanları |

Ham eşitlik: 479 veri/index dosyası. (E1a kabulündeki okuma notu: "480/480 dosya eşit"
dosya kümesi eşitliğidir; ham eşitlik manifiesta istisnalı 479'dur.)

## Sayılar (ölçüldü)

- Vaka: 297 (60 canonical + 237 derived); evaluator kayıt satırı: 594
  (rules-baseline 297, evidence-graph-baseline 297; canonical 120 + mutated 474).
- Karar, hedef, vaka sayısı, metrik farkı: yok (records/analysis ham eşit).
- Yeni çıktı hash envanteri: `run-outputs.sha256` (480 dosya, yol-sıralı).

Tam run dizini `/tmp/sloplab-e1b-ihv1hN/` içinde kalır (`run/`, `logs/`); `/tmp` kalıcı
arşiv değildir. Golden uydurulmadı/güncellenmedi; bu paket farklı bir analiz sürümü değildir.
