# Issue 05 — Bütünleşik kapanış doğrulaması

Yeni özellik eklenmedi; kabul edilmiş E0–E5 paketlerinin birlikte aynı
sözleşmeleri koruduğu doğrulandı. Ortak kurallar:
[worker teslim protokolü](../../../issue-05-worker-delivery-protocol.md).

## İki uçtan uca run

- Kök A: `/tmp/sloplab-int-a-tgLe3X/run`, kök B: `/tmp/sloplab-int-b-laUuV5/run`
  (farklı yeni geçici kökler; `/tmp` kanıt sayılmaz, yeniden üretim komutları
  ve hash envanterleri buradadır).
- Aynı sabit config (`experiments/configs/deterministic-study-v0.2.yaml`),
  aynı çalışma ağacı (`9960f4f` + teslim edilmemiş E2–E5 çalışması).
- Karşılaştırma politikası koşulardan önce yazıldı (`diff-policy.md`):
  izinli alanlar yalnız `manifest.{started_at,finished_at}` ve bunun
  zorunlu sonucu olan completion `manifest.json` hash girdisidir.
- Gözlem: dosya kümeleri eşit; bu alanlar dışında **sıfır fark**.
- Ek bağımsız denetimler: hash zinciri 10/10 (`manifest.suite_hash` →
  suite-index → recipe → records/outcomes → versioned analiz + coverage
  denklemleri + defter/index uzlaşması 280/237/297/60); fake-transport
  pilot koşusu (sayaçlar, failed-dışlama, coverage görünürlüğü); kesik /
  karışık / stale negatif fixture redleri (crafted diff'lerle — deterministik
  run'lar arası ham takas etkisizdir, çünkü bayt-aynıdır).

## Kabul karşılığı

- Politika-dışı deterministik fark: yok.
- Sayaçlar/ledger/index uzlaştı; failed/not_run metriğe girmez, eksik
  coverage (`metric_coverage`, tanımsız nedenleri) görünür.
- Strict okuyucu negatifleri reddeder; tarihsel envanter 0 fark; yeni
  sürümler ayrı (`analysis-v1.json` şema 2, `span_model full-item-v1`,
  paket `0.2.2` sabit).
- Tam offline paket **404 passed**; ruff check/format (tüm ağaç), mypy
  (51 dosya), `git diff --check` temiz. Kabul sözleşmesi bozulması
  bulunamadı (bloklayıcı bulgu yok).

## Açık bilimsel kararlar (kullanıcıya ait)

Ana estimand seçilmedi; parent-eşit ağırlık seçilmedi (case-weighted
betimsel sonuç adlandırıldı); bootstrap bağımsızlık varsayımı ve authored
boyut hedefleri kararlaştırılmadı; yeni CI yöntemi eklenmedi. Analiz
çıktıları bu kararlar verilmeden nihai bilimsel tercih olarak okunmamalıdır.

## Hükümler

- **Canlı pilot hazır DEĞİL.** E0–E5 teknik kapıları birlikte yeşil
  olmasına rağmen: bilimsel kararlar açık, sağlayıcı davranışı/maliyeti
  ölçülmedi ve uydurulmadı, canlı yol hiç çalıştırılmadı. Hazırlık,
  bu üçü birlikte değerlendirilmeden ilan edilemez.
- **E6 koşullu gereksinimi TETİKLENMEDİ.** Tek interpreter kanıtı var;
  çapraz-ortam garantisi verilmedi; ölçülmüş anlamlı darboğaz yok
  (optimizasyon/havuz önerisi gerekçelendirilmedi). E6, profili
  gerekçelendiren ölçümle çalıştırılır.
