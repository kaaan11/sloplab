# E4a — İnceleyici düzeltmesiyle kabul

Tarih: 2026-09-10. **E4a, ana inceleyici düzeltmesinden sonra kabul edildi.**

## Karar

E4a presentation susceptibility metriğini child-parent karar farklarının
case-weighted ortalaması olarak düzeltiyor. Eşit karar çiftleri, parent başına
child sayısı dengesiz olsa bile `0.0` üretiyor. ECE'nin son bini sağdan kapalı;
`0.95/doğru` ve `1.0/yanlış` örneği `0.475` veriyor.

`compute_metrics` girişinde kayıt tekilliği, saklanan `correct` değeri, legacy
failed placeholder ve mutated parent/operator alanları doğrulanıyor. Her metrik
uygun gözlem/çift sayısını, dışlanan veya çözülemeyen girdileri ve tanımsızlık
nedenini `metric_coverage` altında taşıyor. Ham karar ve hedef kayıtları
değişmiyor; ana estimand, parent-eşit ağırlık ve yeni CI seçimi yapılmıyor.

## İnceleyici düzeltmesi

Worker'ın parent karar haritası yalnız `case_id` ile anahtarlanmıştı. Aynı vaka
birden çok repeat içerdiğinde son canonical karar önceki repeatlerin parent'ı
olarak da kullanılabiliyordu. Bağımsız karşıörnekte her repeat içinde parent ve
child kararı aynı olmasına rağmen susceptibility `0.5` çıktı; beklenen değer
`0.0` idi.

Parent eşlemesi `(case_id, evaluator_name, repeat_index)` kimliğine bağlandı.
Aynı kimlik hem susceptibility hem robustness çiftlerinde kullanılıyor. Yeni
regresyon testi iki repeat içindeki iki doğru çifti ayrı çözüyor ve coverage'ın
iki pair bildirdiğini doğruluyor.

Worker'ın `docs/reviews/issue-05/E4a/` kanıtları değiştirilmeden korunuyor.

## Bağımsız doğrulama

- Worker kayıtları: 231 hedefli ve 339 tam offline test; ruff, format ve mypy
  başarılı; teslim run envanteri 484/484 doğrulanmış.
- İnceleyici düzeltmesi sonrası metrik/scoring/calibration kümesi: **22/22**.
- Tam offline paket: **340/340**.
- Ruff, format, mypy ve `git diff --check`: temiz.
- Yeni deterministik review çalışması:
  `/tmp/sloplab-e4a-review-ce7GWR/run`; 297 vaka, iki evaluator ve 594 kayıt.
  Worker E4a çalışmasıyla 484 dosyalık küme aynı, 482 dosya ham eşit. Yalnız
  izinli zaman alanlarını taşıyan `manifest.json` ve onun hash'ini taşıyan
  `completion.json` farklı; analiz ve rapor dahil diğer bütün dosyalar eşit.
  Strict doğrulama başarılıdır. `/tmp` kalıcı arşiv değildir.

## Kapsam sınırı

Bu kabul E4a'nın betimsel metrik sözleşmesini ve karşıörnek düzeltmelerini
kapatır. Analiz sürümü/records hash bağı, tarihsel yeniden hesaplama, operatör
uygunluğu ve stale cache reddi E4b kapsamındadır. Canlı pilot henüz
başlatılabilir ilan edilmedi. Sıradaki paket
[E4b görev dosyasıdır](../../issue-05-E4b-task.md).
