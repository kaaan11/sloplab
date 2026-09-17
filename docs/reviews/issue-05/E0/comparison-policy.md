# E0 karşılaştırma politikası (çıktılar görülmeden yazıldı)

Tarih: 2026-09-09. Kapsam: `sloplab study experiments/configs/deterministic-study-v0.2.yaml --out <dir>`
akışının ürettiği bundle. Dayanak: `src/sloplab/experiments/study.py:49-114`
(materialize → build_cases → evaluator sırasıyla records → manifest),
`src/sloplab/experiments/runner.py:103-118` (`manifest.json` + `records.jsonl` yazımı),
`src/sloplab/cli/main.py:325-401` (analysis.json / results.csv / report.md türetimi),
`src/sloplab/mutations/materialize.py:147-175` (suite-index.jsonl + adversarial ağacı).

CLI `study` çıktısı (gözlemlenen + koddan beklenen): `suite-index.jsonl`,
`adversarial/<parent>/<case>/{report.md,mutation-manifest.yaml}`, `records.jsonl`,
`manifest.json`, `analysis.json`, `results.csv`, `report.md`.

## A/B (iki yeni çalışma) — ham eşitlik esastır

| Çıktı | Politika |
| --- | --- |
| `records.jsonl` | Ham bayt ve satır sırası eşitliği (`cmp`). Sıralama/satır atlama yok. Gerekçe: `build_cases` case_id'ye göre sıralar (`harness.py:123`), evaluator sırası config sırasıdır (`study.py:83-91`); sıra sözleşmenin parçasıdır. |
| `adversarial/` | Önce iki yönlü göreli dosya kümesi eşitliği, sonra her dosyanın ham SHA-256 eşitliği. Farklı dosya varsa kapsam dışı bırakılmaz. |
| `suite-index.jsonl` | Ham SHA-256 eşitliği + yapılandırılmış alan farkı (header + satırlar). `corpus_root`/yol alanları otomatik silinmez; aynı cwd'den çalıştırıldıkları için A/B'de eşit beklenir. |
| `analysis.json` + CLI'nin ürettiği diğer analiz dosyaları | Dosya varlığı + ham hash. Gerekirse alan bazında fark; float yuvarlama ile kapatma yok. Bootstrap `base_seed`'den seed'li (`main.py:374-382`), A/B'de eşit beklenir. |
| `report.md`, `results.csv`, diğer çıktılar | Ham karşılaştırma. Fark çıkarsa veri/sunum düzeyi olarak sınıflandırılır. |
| `manifest.json` | Ham fark saklanır + alan bazlı karşılaştırma. Önceden değişken ilan edilen alanlar: `started_at`, `finished_at` (iki ayrı `utc_now_iso()` çağrısı, `study.py:104-105`). `commit_sha`, `config_hash`, `suite_hash`, `base_seed`, `evaluators`, `corpus_root` kimlik alanıdır; örtülmez, farkıating edilir. |

A/B'de `records.jsonl`, `adversarial/`, `suite-index.jsonl`, `analysis.json`,
`results.csv`, `report.md` için açıklanmayan her ham fark determinism
başarısızlığıdır. `manifest.json`'da yalnız `started_at`/`finished_at` farkı
beklenir; başka alan farkı açıklanır.

## Tarihsel (eski study-v02) vs yeni (run-a) — farklar belgelenir, normalize edilmez

Aynı ham kontroller uygulanır, ancak aşağıdaki bilinen kaynak farkları önden
değişken/farklı kabul edilir ve ayrıca raporlanır (eşitlik sayılmaz):

- `manifest.json`: `commit_sha` (eski `14547a0…`, yeni HEAD `9960f4f…`),
  `corpus_root` (eski mutlak `/home/kaan/ai-workspaces/sloplab/corpus`, yeni çözülmüş mutlak yol),
  `started_at`/`finished_at`, muhtemel `config_hash`/`suite_hash`/`evaluator_config_hashes` farkları.
- `suite-index.jsonl` header `corpus_root` mutlak yol farkı.
- Şema/üretici sürüm farkı varsa (`generator_version`) ayrıca yazılır.
- Normalize (ör. zaman/yol maskeli) karşılaştırma yapılırsa sonucu ham bayt
  eşitliği diye adlandırılmaz; iki sonuç ayrı satırlarda tutulur.
- Eski dizinde olup yenide olmayan / yenide olup eskide olmayan dosyalar
  (ör. beklenen `metrics-*.json` yokluğu/varlığı) kapsama dahil edilir, dışlanmaz.

## Genel kurallar

- `cmp`/`diff`'in fark bildiren exit code'u çalıştırma hatasıyla karıştırılmaz.
- Başarısız study'nin kısmi çıktısı başarılı çalışma gibi analiz edilmez.
- Karşılaştırma yardımcıları `helpers/` altındadır; ham hash listeleri
  `inventories/` altındadır. Çıktılar görülüp politika daraltılmaz; değişiklik
  gerekirse eski sonuç korunarak gerekçesiyle revize edilir.
- Uygulama notu (rev3): `helpers/compare_e0.py` rev3, yukarıdaki politikayı uygular:
  A/B'de 480 dosyalık tam küme + ham hash; suite-index.jsonl A/B'de ham bayt eşitliği
  zorunlu (manifest allowlist `{started_at, finished_at}`); tarihselde tam küme +
  allowlist-dışı her fark çıkış kodunu bozar (manifest `{commit_sha, corpus_root,
  started_at, finished_at, suite_hash}`, suite-index header'da yalnız `corpus_root`,
  gövde ilk `b'\n'` sonrası ham baytlarla — satır sonları dahil). `splitlines()`
  normalizasyonu karar vermez; LF/CRLF farkı reddedilir. Kanıt:
  pozitif `/tmp/sloplab-e0-zVHDyy/logs/compare-rev3.stdout.log` (`RESULT: OK`, exit 0);
  negatif A/B `compare-neg-ab.stdout.log` ve negatif tarihsel-gövde
  `compare-neg-hist.stdout.log` (ikisi de exit 1, `rejected`). Negatif fikstürler
  `/tmp/sloplab-e0-crlf-Q1PqPf/` (`ab-crlf/`, `old-crlfbody/`; yol
  `/tmp/sloplab-e0-zVHDyy/logs/neg-root.txt` içinde).
