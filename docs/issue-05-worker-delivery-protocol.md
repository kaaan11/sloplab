# Issue 05 — Worker teslim protokolü

Bu protokol E2b ve sonrasındaki bütün görev dosyalarının ortak parçasıdır.

## Çalışma ilkeleri

- Kök `/home/kaan/sloplab`; varsa `AGENTS.md` önce okunur.
- Önceki kabul edilmiş dirty-worktree değişiklikleri ve kullanıcı dosyaları korunur.
- Görev dosyasındaki okuma/değişiklik sınırı dışına yalnız zorunlu bağlantı için çıkılır;
  kapsam genişlemesi kapanışta dosya ve gerekçeyle belirtilir.
- Tarihsel `records`, `analysis`, rapor ve türevlerin üzerine yazılmaz. Canlı API/ağ
  kullanılmaz. Test doubles/fake transport kullanılır.
- Bilimsel seçim gereken noktada sessiz varsayım yapılmaz; uygulama durdurulmadan
  mümkün olan mühendislik kısmı tamamlanır ve karar açık bırakılır.
- Alt ajan başlatılmaz. Yeni framework veya genel amaçlı altyapı eklenmez.

## Uygulama ve doğrulama

Önce mevcut davranış ve tüketiciler `rg` ile bulunur. Kabul ölçütünü karşılayan en
küçük değişiklik yapılır. İlgili regression testleri, değişen dosyalarda ruff
check/format ve mypy çalıştırılır; kabul öncesi tam offline test paketi bir kez
çalıştırılır. Test assertions kaldırılarak veya yalnız genel exception beklenerek
geçirilmez. Mevcutsa `apply_patch` kullanılır.

Davranış eşdeğerliği gereken teslimlerde son kabul referansına karşı yeni offline
run üretilir. Ham eşitlik, semantik eşitlik ve bilinçli şema farkları ayrı yazılır.
`/tmp` kalıcı arşiv sayılmaz.

## Kanıt dizini

Teslim `docs/reviews/issue-05/<paket>/` altında şunları içerir:

- `README.md`: uygulanan davranış, değişen/yeni dosyalar, test sonuçları, açık kapsam;
- `commands.jsonl`: komut, cwd, exit code, log yolu ve kısa amaç;
- `comparisons.md`: önceki referans, yöntem, ham/semantik farklar ve hüküm;
- görev sözleşmesini açıklayan en az bir konu belgesi;
- başlangıç/bitiş hash veya durum envanteri, gerçek diff ve gerekli stdout/stderr logları;
- üretilen run varsa `run-outputs.sha256`.

Worker kendi teslimini “tamamlandı” diye yazabilir; nihai kabul ana inceleyicinin
`docs/reviews/issue-05/<paket>-acceptance.md` kaydıyla verilir. Bir üst fazı veya
canlı pilotu hazır ilan etmez.
