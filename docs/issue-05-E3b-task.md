# E3b — Legacy okuma, materialization defteri ve kontrollü yayın

Durum: Revizyon gerekli. Karar:
[E3b incelemesi](reviews/issue-05/E3b-acceptance.md). Önkoşul:
[E3a kabulü](reviews/issue-05/E3a-acceptance.md). Ortak kurallar:
[worker teslim protokolü](issue-05-worker-delivery-protocol.md).

## Hedef

Bütün tüketicileri E3a doğrulayıcı reader'ına bağla; eski şemaya açık legacy
okuma yolu veya açıklayıcı hata sağla. Materialization planlarının sonuçlarını
eksiksiz kaydet ve ortak study koordinasyonunda deterministik vaka hatasını yanlış
karara çevirmeden izole et.

## Sözleşme

Her materialization planı tam bir kez `written`, `no_op`, `duplicate`,
`safety_blocked` veya `error` durumuna düşer. Popülasyon değişikliği sessiz kalmaz;
planlanan/üretilen/seçilen sayılar uzlaşır. Deterministik evaluator exception'ı
vaka/evaluator outcome'u olarak görünür olabilir, fakat config/programlama hatası
geniş catch ile yutulmaz. Teknik bundle tamamlanması ile bilimsel coverage
yeterliliği ayrı alanlardır.

CLI `compare`, reporting ve analiz cache'i strict/legacy ayrımını aynı şekilde
uygular. Legacy okuma tarihsel dosyayı yeniden yazmaz ve yeni şema garantisi
vermez. E4 formül düzeltmesi, E5 kaynak düzenlemesi kapsam dışıdır.

## Kabul

- Tüm okuyucular E3a bütünlük sınırını kullanır; bypass regression testi vardır.
- Legacy fixture açık modda okunur veya kararlı, açıklayıcı hata verir.
- Beş materialization durumu ve sayaç denklemleri testlidir.
- Kesinti/duplicate/safety-blocked yolları popülasyon kaybını görünür kılar.
- Beklenen evaluator failure izole edilir; beklenmeyen program/config hatası yükselir.
- `bundle_complete` ile `coverage_sufficient` birbirine eşitlenmez.
- E0/E1 deterministik başarı verileri açıklanmayan biçimde değişmez; tam test geçer.

Teslim `legacy-reader-contract.md` ve `materialization-outcomes.md` içermelidir.
