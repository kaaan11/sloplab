# Bütünleşik kapanış — koşu-öncesi fark politikası

Yazım zamanı: her iki run üretilmeden önce. İki run aynı sabit config
(`experiments/configs/deterministic-study-v0.2.yaml`), aynı mevcut
çalışma ağacı (`9960f4f` + teslim edilmemiş E2–E5 çalışması) ve farklı
yeni geçici köklerle üretilecektir.

## İzin verilen değişken metadata alanları (kapsamlı liste)

- `manifest.json`: yalnız `started_at`, `finished_at`.
- `completion.json`: yalnız `manifest.json` girdisinin hash değeri
  (izinli zaman alanlarının zorunlu sonucu); haritadaki diğer bütün
  girdiler bayt-eşit olmalıdır (ayrı doğrulanır).
- Diğer her dosya: bayt-eşit olmalıdır.

## Politika dışı her farkın rapor formatı

Dosya + JSON yolu (varsa) + gerekçe. Gerekçesiz fark = kabul ihlali;
sonucu gizlemek için kod veya fixture sessizce değiştirilmez — ayrı
bloklayıcı bulgu kaydedilir.

## Bilinen beklenen farklar (önceden ilan)

- Yok: iki run arasında yukarıdaki alanlar dışında fark beklenmez.
  E1e-tarihsel karşılaştırmadaki bilinen farklar (üç şema eki, E4a
  türevleri, B1 etki kümesi) bu runlar-arası politikaya dahil değildir;
  onlar ayrı referans karşılaştırmasıdır.
