# E4b — Revizyon gerekli

Tarih: 2026-09-10. **E4b bu teslimle kabul edilmedi. E4 açık kaldı.**

## Doğrulanan kazanımlar

Teslim ayrı `analysis-v1.json` adı, analiz tanım sürümü ve records dosyasının
SHA-256 bağını ekliyor. Strict bundle kapısı, records hash/satır sayısı, scored
sayıları ve sürüm uyuşmazlığı okuyucuda denetleniyor. CLI compare ile report aynı
sürümlü okuyucuyu kullanıyor. Tarihsel yeniden hesaplama ve operatör uygunluğu
belgeleri kapsam sınırlarını açıkça kaydediyor.

Ana inceleyicinin yeni E4b test kümesi çalıştı: **13/13**. Worker README'sindeki
“14 yeni test / 353 tam test” hesabı güncel ağaçla uyuşmuyor: üç yeni dosyada
9 + 2 + 2 = 13 test var; E4a inceleyici testi dahil güncel baz 340 olduğundan
beklenen tam toplam 354'tür. Bu sayım farkı tek başına ret nedeni değildir.
Worker kanıtları `docs/reviews/issue-05/E4b/` altında değiştirilmeden korunuyor.

## Bloklayıcı 1 — failed coverage doğrulanmıyor

`read_versioned_analysis` records satırlarından yalnız evaluator başına `scored`
sayısını yeniden hesaplıyor. Gömülü `failed` alanını `outcomes.jsonl` ile
karşılaştırmıyor; outcomes dosyasının hash'i, satır sayısı ve vaka/evaluator
kimlikleri analiz zarfına bağlı değil.

Bağımsız karşıörnekte geçerli E4b çalışmasının
`coverage.evidence-graph-baseline.failed` değeri `999` yapıldı ve strict bundle
completion yeniden üretildi. Okuyucu sahte coverage'ı kabul etti:

```text
evidence-graph-baseline {'failed': 999, 'scored': 297}
```

Bu davranış briefteki selection/outcome coverage bağını ve coverage uyuşmazlığı
reddini karşılamıyor.

## Bloklayıcı 2 — tamamen başarısız evaluator görünmez oluyor

CLI study sürümlü coverage ve bundle alanlarını yalnız `by_evaluator`, yani en az
bir başarılı `records.jsonl` satırı bulunan evaluatorlardan kuruyor. Bir evaluator
bütün vakalarda tipli `EvaluationFailure` üretirse `outcomes.jsonl` içinde
bulunmasına rağmen sürümlü analizin evaluator kümesinden tamamen düşüyor. Böylece
`scored=0`, `failed=N` ve bilimsel yetersizlik görünür biçimde raporlanmıyor.

## Bloklayıcı 3 — gömülü metrikler records ile yeniden doğrulanmıyor

Okuyucu records hash'inin belgeye uyduğunu denetliyor, fakat `bundles` içindeki
metrik değerlerini aynı records üzerinden E4a tanımıyla yeniden hesaplayıp
karşılaştırmıyor. Analysis içindeki bir metrik değiştirilip completion yenilenirse
records bağı hâlâ geçerli görünür. E4b'nin “doğrulanmış metrikler records kümesi ve
analiz tanımıyla ayrışamaz” sözleşmesi için bu iç tutarlılık kontrolü gereklidir.

Bağımsız karşıörnekte `decision_accuracy` değeri `0.123456` yapılıp completion
yenilendi ve okuyucu bu değeri kabul etti:

```text
evidence-graph-baseline 0.123456
```

## Gerekli revizyon

Sürümlü analiz records, outcomes ve selection kapsamını birlikte bağlamalı;
okuyucu scored/failed/planlanan sayıları ve evaluator kümesini bu kaynaklardan
yeniden türetmelidir. Sıfır başarılı evaluator açık bir coverage ve tanımsız
metrik paketiyle korunmalıdır. Gömülü E4a metric bundle'ları records üzerinden
yeniden hesaplanan değerlerle uyuşmadığında okuyucu reddetmelidir.

Revizyon görevi: [E4b-r1](../../issue-05-E4b-r1-task.md).
