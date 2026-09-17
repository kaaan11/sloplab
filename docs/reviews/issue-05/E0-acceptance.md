# E0 — Ana inceleyici kapanış kararı

Tarih: 2026-09-09. İnceleyici: Astra. Durum: **E0 kabul edildi; G0 geçti.**

Bu karar `E0/` tesliminin rev3 karşılaştırma yardımcısına ve mevcut yerel artefaktlara dayanır. E0'ın orijinal envanter ve günlükleri değiştirilmemiştir.

## Bağımsız doğrulama

- `python3 -B docs/reviews/issue-05/E0/helpers/compare_e0.py /tmp/sloplab-e0-zVHDyy/run-a /tmp/sloplab-e0-zVHDyy/run-b experiments/results/deterministic/study-v02` çalıştırıldı: exit 0, `RESULT: OK`.
- Her çıktı ağacı 480 dosya içeriyor; A/B'de yalnız manifesto zamanları farklı. Tarihsel karşılaştırmada index header'ındaki korpus yolu ve açıklanmış beş manifesto alanı farklı; diğer dosyalar eşit.
- Bellek içi üç bağımsız karşıörnek kontrol edildi: A/B LF/CRLF farkı reddedildi; tarihsel yalnız korpus yolu farkı kabul edildi; yol farkıyla birlikte gövde satır sonu farkı reddedildi. Kontrollerin tamamı geçti.
- Başlangıç ve tamamlanmış bitiş envanterleri karşılaştırıldı; 32 kaynak/config, 120 canonical korpus ve 480 tarihsel artefakt girdisinin güncel hash'leri de doğrulandı. Uyumsuzluk yok.
- Önceki incelemede doğrulanan 297 vaka / 594 evaluator kaydı sonucu geçerliliğini koruyor. Study ve pytest bu kapanışta tekrar çalıştırılmadı; mevcut artefaktlar kontrol edildi. Önceki test günlüğü 10 geçen test kaydediyor.

## Önceki eksiklerin durumu

1. Tam bitiş envanterleri ve gerçek ölçüm zamanı eklenmiş. İki satırlık eski envanter korunmuş ve hükümsüz olduğu belirtilmiş.
2. Tüm çıktı dosyalarının kümesi ve tarihsel açıklanamayan farklar karşılaştırma kararına katılıyor. Rev2'de kalan suite-index ham bayt kontrolü rev3'te düzeltilmiş.
3. Mikro kontrollerin kaynakları ve yeniden çalıştırma komutları teslimde. Komut kaydı eski denemelerin bir bölümünün aynı günlük yoluna yazıldığını açıkça belirtiyor; kaybolan günlükler yeniden elde edilmiş sayılmıyor.

E0 yardımcıları mevcut karakterizasyonu doğrulamak için kabul edilmiştir; genel amaçlı, bozuk veya kasıtlı değiştirilmiş bütün bundle'ları doğrulayan bir okuyucu sözleşmesi olarak onaylanmış değildir. Bu konu E3'tür. Başlangıç/bitiş hash eşitliği aradaki her anı gözlemlemez; mevcut kanıtta girdi değişimi göstergesi yoktur.

İlk iki incelemede bulunan eksikler sayısal sonuçları çürütmemiştir. Bu kapanışta uygulama koduna veya worker yardımcısına ek düzeltme gerekmedi.

## Sonraki teslim

[E1a görev dosyası](../../issue-05-E1a-task.md): deterministik study için desteklenmeyen ayarlar ve bilinmeyen evaluator adlarında yan etkiden önce ret. E1'in tamamı bu paketle kapanmayacak; etkili tarif kimliği, değişmez vaka girdisi ve prompt bağı sonraki dar paketlerde ele alınacak.
