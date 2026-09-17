# E4a — Metrik sözleşmeleri ve analitik karşıörnek düzeltmeleri

Durum: İnceleyici düzeltmesiyle kabul edildi. Kabul kaydı:
[E4a kabulü](reviews/issue-05/E4a-acceptance.md). Önkoşul:
[E3b-r1 kabulü ve E3 kapanışı](reviews/issue-05/E3b-r1-acceptance.md).
Ortak kurallar: [worker teslim protokolü](issue-05-worker-delivery-protocol.md).

## Hedef

Her metrik için uygun kayıt, analiz birimi, pay/payda, eksik veri, sıfır payda ve
ağırlık sözleşmesini yaz. Paired susceptibility ve ECE için plandaki küçük
karşıörnekleri önce kırmızı test olarak doğrula, sonra formülü düzelt.

## Zorunlu örnekler

- Parent ve child kararları her çiftte eşitse, child sayıları parentlar arasında
  farklı olsa bile paired susceptibility `0` olmalıdır. Parent/pair bağı yoksa
  metrik neden belirterek tanımsızdır.
- `0.95/doğru` ve `1.0/yanlış` iki uygun gözlem son bine girer; ECE `0.475` olur.
  Güven `1.0` hiçbir binin dışında kalamaz ve her kayıt tam bir bine girer.
- Failed/not_run outcome karar doğruluğu, ECE veya geçerli karar birliğine girmez.
- Kayıt tekilliği, `correct` alanının hesaplanan kararla uyumu, selection ve parent
  bağları reader sınırında doğrulanır.

Ana estimand, parent-eşit ağırlık, bootstrap bağımsızlık varsayımı ve authored
boyut hedeflerinin bilimsel geçerliliği bu pakette seçilmez. Mevcut case-weighted
betimsel sonuç korunabilir fakat açıkça adlandırılır. Yeni CI yöntemi ekleme.

## Kabul

Karşıörnekler beklenen exact/approx değerlerle geçer; uygunsuz veri sessizce
paydadan kaybolmaz; her metrik coverage ve undefined reason taşır. Başarı yolundaki
ham kararlar/hedefler değişmez. Hedefli ve tam offline test paketi geçer.

Teslim `metric-contracts.md` ve karşıörneklerin eski/yeni sonuç tablosunu içerir.
