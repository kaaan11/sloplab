# E3b-r1 — İnceleyici düzeltmesiyle kabul ve E3 kapanışı

Tarih: 2026-09-10. **E3b-r1, ana inceleyici düzeltmesinden sonra kabul edildi. E3 kapatıldı.**

## Karar

E3b-r1 tarihsel legacy paket ile kesilmiş yeni yayını kalıcı
`publish-in-progress.json` durumu üzerinden ayırıyor. Study ve pilot yazarları
çıktı üretiminden önce yayın döngüsünü açıyor; completion ve in-progress birlikte
bulunsa dahi strict reader, sınıflandırıcı ve tüketici kapısı paketi reddediyor.
Başarılı yayın completion yazıldıktan sonra in-progress işaretinin kaldırılmasıyla
görünür oluyor.

E3b'de kabul edilen materialization outcome defteri, evaluator failure izolasyonu,
legacy tüketici geçişi ve teknik bundle/bilimsel coverage ayrımı korunuyor.
Tarihsel fixture okumalarının kaynak ağacı değiştirmediği regresyon testiyle
sabitleniyor.

## İnceleyici düzeltmesi

Worker uygulamasındaki `begin_publish` önce eski `completion.json` dosyasını
siliyor, ardından in-progress işaretini yazıyordu. Bu iki işlem arasındaki dar
pencerede eski veri marker'sız kalıyor ve `open_result_dir` tarafından yeniden
legacy olarak kabul edilebiliyordu.

Sıra düzeltildi: in-progress işareti önce yazılıyor, okuyucular bu işareti ilk
kontrol ettiği için eski completion hâlâ mevcut olsa bile tüketim reddediliyor;
eski completion bundan sonra kaldırılıyor. Kullanılmayan ve bu güvenceyi
sağlamayan `invalidate_completion` yardımcısı kaldırıldı. Yeni regresyon testi,
completion'ın `unlink` edildiği anda sınıflandırmanın `incomplete` ve tüketici
kapısının `rejected` olduğunu doğrudan gözlüyor.

Worker'ın `docs/reviews/issue-05/E3b-r1/` kanıtları değiştirilmedi. Teslimde
belgelenen başlangıç kanıtı kurtarma olayı nedeniyle worker provenance'ı tam
doğrudan kayıt gücünde değildir; E3b son hashleriyle çapraz doğrulanmış rekonstrüksiyon
olarak değerlendirilmiştir. Kabul, ana inceleyicinin güncel kod ve davranış
üzerindeki bağımsız kontrollerine dayanır.

## Bağımsız doğrulama

- Worker kayıtları: 209 hedefli ve 331 tam offline test; ruff, format ve mypy
  başarılı; teslim run envanteri 484/484 doğrulanmış.
- İnceleyici düzeltmesi sonrası publish/reader/bundle regresyonları: **32/32**.
- Tam offline paket: **332/332**.
- Ruff, format, mypy ve `git diff --check`: temiz.
- Yeni deterministik review çalışması:
  `/tmp/sloplab-e3b-r1-review-4j6EZv/run`; 297 vaka, iki evaluator ve 594 kayıt.
  Paket strict doğrulamada `complete`, in-progress artığı yok. Worker koşusuyla
  484 dosyalık küme aynı ve 482 dosya ham eşit. Yalnız izinli zaman alanlarını
  taşıyan `manifest.json` ile onun hash'ini taşıyan `completion.json` farklı;
  diğer completion içeriği eşit. `/tmp` kalıcı arşiv değildir.

## E3 kapanış sınırı

E3a ile completion/hash sınırı ve strict reader çekirdeği; E3b serisiyle bütün
tüketicilerin strict/legacy geçişi, kesilmiş yayın durumu, materialization outcome
defteri, evaluator failure izolasyonu ve coverage ayrımı kapandı.

Metrik formülleri, analiz uygunluğu ve sürümlü yeniden hesaplama E4 kapsamındadır.
Canlı pilot henüz başlatılabilir ilan edilmedi. Sıradaki paket
[E4a görev dosyasıdır](../../issue-05-E4a-task.md).
