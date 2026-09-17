# E3b-r1 — Yayın durum makinesi (publish-state-contract.md)

## Durumlar

Bir bundle dizini her an tam bir durumdadır (`classify_bundle`):

- `complete`: in-progress YOK, completion VAR ve doğruluyor.
- `incomplete`: in-progress VAR (yayın sürüyor ya da kesildi) veya
  completion VAR ama bozuk veya hiçbir şey tanınmıyor.
- `legacy`: in-progress YOK, completion YOK, ama legacy biçimli dosyalar
  VAR (E3a-öncesi tarihsel paket).

Sınıflandırma durum-bazlıdır; dosya adı sezgiseli kullanılmaz: kesilmiş
yeni yayın (manifest+records+identity+recipe, işaretsiz) artık
`legacy` DEĞİL `incomplete` görünür — çünkü gerçek yeni yazım her zaman
iz bırakır (aşağıda).

## Geçişler (study ve pilot)

```
begin_publish:  completion? sil → publish-in-progress.json yaz
                  (study: koşucu preflight sonrası, ilk mutasyondan önce;
                   pilot: zincir/prompt doğrulaması sonrası, ilk dispatch öncesi)
     ↓
[yayın: veri dosyaları yazılır; kesinti → incomplete kalır]
     ↓
finish_publish: completion.json yaz (veri dosyaları + tür asgarisi) →
                publish-in-progress.json sil (EN SON)
     ↓
complete (yalnız bundan sonra)
```

Okuyucu sırası (`verify_bundle`, `open_result_dir`): ÖNCE in-progress
kontrolü (varsa `BundleError` — completion geçerli olsa bile), SONRA
completion doğrulaması. Completion dosya haritası protokol işaretlerini
kapsamaz (yalnız veri dosyaları; yazarlar başka geçici dosya üretmez).

## Yayıncı-iç okuma kuralı

Aynı sürecin kendi ara çıktısını okuması (CLI study'nin analiz öncesi
kayıt okuması) tüketim değildir: yayın-ortasında gerçekleştiği için kapı
onu kilitlerdi. Bu okumalar kapıdan geçmez; gerekçesi kodda kayıtlıdır.
Yayın-dışı her okuma (compare, report, llm_bench, sonraki süreçler)
kapıdan geçer. Yayın sırasında aynı baytlara yönelen kapı okuması
reddedilir (testle sabit: kilitlenme yok, sessiz tüketim yok).

## Yeniden yazım ve kesinti

- Eski tamamlanmış dizine yeniden yazım: `begin_publish` eski
  completion'ı kaldırır + in-progress yazar → çalışma boyunca
  `incomplete`; `finish_publish` sonrası yeniden `complete`, artık dosya
  kalmaz.
- Completion yazımı ile son adım arası kesinti: completion + in-progress
  birlikte kalır → `incomplete`, bütün okuyucular reddeder.
- Doğrulama hatası (coverage tutmazlığı vb.) yayını yarıda keserse
  in-progress yerinde kalır: başarısız yayın tüketilemez.
- Tarihsel (E3a-öncesi, işaretsiz) paketler açık legacy modda okunur,
  yeniden yazılmaz.
