# E4b — Sürümlü analiz yayını ve tarihsel yeniden hesaplama

Durum: Revizyon gerekli. Karar:
[E4b incelemesi](reviews/issue-05/E4b-acceptance.md). Önkoşul:
[E4a kabulü](reviews/issue-05/E4a-acceptance.md). Ortak kurallar:
[worker teslim protokolü](issue-05-worker-delivery-protocol.md).

## Hedef

Doğrulanmış E4a metriklerini strict reader üzerinden sürümlü analiz çıktısına
bağla. Analiz çıktısı kaynak kayıt kümesinin hash'i, selection/outcome coverage'ı
ve analiz tanım sürümüyle ayrışamaz olsun. Eski `analysis.json` üzerine yazma.

## Çalışma

Tarihsel kabul referansındaki ham kayıtlar üzerinde bağımsız yeniden hesaplama
yap. Legacy ve yeni değerleri metrik bazında fark/neden tablosuna koy. Mevcut
operatörler için ölçüm uygunluğu tablosu üret; karar değişmezliğini kalite
nötrlüğü olarak yorumlama. Parent gerektiren alt gruplara eşleşme bağlamı sağla,
sağlanamıyorsa undefined reason yaz.

Rapor ve CLI tüketicileri analiz sürümünü/hash bağını doğrular. Stale cache,
başka records dosyasıyla karıştırılmış analiz ve coverage uyuşmazlığı reddedilir.
Ana estimand/CI yöntemi kullanıcı tarafından ayrıca kararlaştırılmadıysa yeni bir
nihai bilimsel tercih ilan edilmez.

## Kabul

- Yeni analiz eski dosyayı değiştirmeden ayrı ad/sürümle yazılır.
- Records hash veya analiz sürümü değişince cache kabul edilmez.
- Tarihsel yeniden hesaplama tekrar üretilebilir; tüm farkların nedeni kayıtlıdır.
- CLI/report aynı doğrulanmış analizi tüketir.
- Ham tarihsel records ve target baytları değişmez; tam offline paket geçer.

Teslim `analysis-version-contract.md`, `legacy-vs-current-analysis.md` ve
`operator-metric-eligibility.md` içermelidir.
