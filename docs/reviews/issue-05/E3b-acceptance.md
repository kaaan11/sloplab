# E3b — Revizyon gerekli

Tarih: 2026-09-10. **E3b bu teslimle kabul edilmedi. E3 açık kaldı.**

## Doğrulanan kazanımlar

Worker teslimi beş materialization sonucunu (`written`, `no_op`, `duplicate`,
`safety_blocked`, `error`) kayıt altına alıyor ve defter ile suite index
sayaçlarını uzlaştırıyor. Beklenen `EvaluationFailure` vaka outcome'una
çevrilirken puanlanmış kayıt üretilmiyor; beklenmeyen program hataları yükseliyor.
Pilot manifestosunda teknik bundle tamamlanması ile bilimsel coverage alanları
ayrı tutuluyor.

Worker'ın 21 yeni testi ve ana inceleyicinin aynı hedefli kümesi geçti. Teslim
kanıtları `docs/reviews/issue-05/E3b/` altında değiştirilmeden korunuyor.

## Bloklayıcı bulgu — kesilmiş yeni yayın legacy olarak tüketiliyor

`open_result_dir`, `completion.json` bulunmadığında dizinde legacy şekil
dosyalarından yalnız biri varsa doğrudan `"legacy"` döndürüyor. Yeni study veya
pilot yazımı completion yayımlanmadan kesildiğinde de aynı dosyalar kalır.
Dolayısıyla yeni şemaya ait kesilmiş ara paket, strict doğrulama görmeden legacy
yolundan tüketilebilir.

Bağımsız minimal karşıörnekte işaretsiz `manifest.json`, `records.jsonl`,
`input-identity.json` ve `execution-recipe.json` içeren yeni-study biçimli dizin
için hem `classify_bundle` hem `open_result_dir` `legacy` döndürdü:

```text
classify= legacy
open= legacy
```

Bu davranış E3a'nın “completion marker yokken yeni bundle kabul edilmez”
sözleşmesini ve E3b'nin tüm tüketicileri aynı bütünlük kapısına bağlama kabul
ölçütünü ihlal ediyor. Mevcut bypass testleri bozuk completion işaretini ve kapı
çağrısını sınasa da işaretsiz kesilmiş yeni yayın ile tarihsel legacy ayrımını
sınamıyor.

## Gerekli revizyon

Yeni yayın niyetini tarihsel legacy'den ayıran kalıcı bir in-progress işareti
gerekiyor. Okuyucular bu işaret varken, completion bulunsa bile, paketi
reddetmeli. Yeniden yazım başlamadan önce in-progress görünür olmalı; başarılı
completion güvenli biçimde yazıldıktan sonra en son bu işaret kaldırılmalı.
Completion dosya haritası yayın protokolünün iç işaretlerini kapsamamalı.

Study ve pilot için şu durumlar gerçek tüketici kapılarında test edilmelidir:

- tarihsel işaretsiz paket açık legacy modda okunur;
- yeni yayın kesilirse in-progress kalır ve bütün okuyucular reddeder;
- eski tamamlanmış dizine yeniden yazım başlayınca eski completion tüketilemez;
- completion yazımı ile son publish adımı arasındaki kesinti reddedilir;
- başarılı yayın strict doğrulanır ve in-progress işareti kalmaz.

Revizyon görevi: [E3b-r1](../../issue-05-E3b-r1-task.md).
