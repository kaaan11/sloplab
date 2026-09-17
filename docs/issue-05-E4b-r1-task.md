# E4b-r1 — Outcomes bağlı coverage ve yeniden doğrulanan metrikler

Durum: İnceleyici düzeltmesiyle kabul edildi. Kabul kaydı:
[E4b-r1 kabulü ve E4 kapanışı](reviews/issue-05/E4b-r1-acceptance.md). Önkoşul:
[E4b revizyon kararı](reviews/issue-05/E4b-acceptance.md). Ortak kurallar:
[worker teslim protokolü](issue-05-worker-delivery-protocol.md).

## Hedef

E4b'nin ayrı analiz sürümünü, records hash bağını, tarihsel yeniden hesaplama ve
operatör uygunluğu belgelerini koru. Sürümlü analizi selection + records +
outcomes kaynaklarıyla tam bağla; okuyucu coverage ve E4a metriklerini bu
kaynaklardan yeniden doğrulasın.

## Kapatılacak karşıörnekler

1. `analysis-v1.json` içindeki `failed` sayısı değiştirildikten ve completion
   yenilendikten sonra okuyucu belgeyi kabul ediyor.
2. Bütün vakalarda tipli `EvaluationFailure` üreten evaluator outcomes defterinde
   bulunduğu halde sürümlü analizin evaluator/coverage kümesinden düşüyor.
3. Gömülü metric bundle değeri değiştirilip completion yenilendiğinde records
   hash'i aynı kaldığı için okuyucu sahte metriği kabul ediyor.

## Bağlayıcı sözleşme

- Analiz zarfı records dosyasının yanında outcomes kaynağının varlık/yokluk
  durumunu, varsa yolunu, SHA-256 değerini ve satır sayısını taşımalıdır.
- Selection kapsamı planlanan vaka/evaluator birliğini ve evaluator başına
  `scored + failed` denkliğini açıklamalıdır. Study yolunda `not_run` yoksa bunu
  açık `0` veya eşdeğer kararlı sözleşmeyle belirt.
- Okuyucu records ve outcomes satırlarını ayrıştırıp evaluator kümesini,
  scored/failed sayılarını, vaka kimliklerini, çakışma/tekillik durumunu ve
  planlanan kapsamı yeniden doğrulamalıdır.
- Tamamen başarısız evaluator analizden düşmemeli: `scored=0`, `failed=N`, coverage
  yetersizliği ve tanımsız metrik nedenleri görünür kalmalıdır. Uydurma karar veya
  puanlanmış kayıt üretme.
- `bundles` içindeki E4a metrikleri, bağlı records satırlarından güncel
  `ANALYSIS_DEFINITION_VERSION` ile yeniden hesaplanan metric bundle'larla tam
  uyuşmalıdır; uyuşmazlık `AnalysisError` üretmelidir.
- `analysis.json` ve tarihsel artefaktlar değiştirilmemeli; estimand, ağırlık veya
  CI tercihi eklenmemelidir.

## Kabul ölçütleri

- Değiştirilmiş failed/not_run/planned/selection coverage, tazelenmiş completion
  bulunsa bile reddedilir.
- Outcomes dosyasının değiştirilmesi, başka run'dan alınması, satır düşmesi,
  duplicate vaka/evaluator ve records ile success/failed çakışması reddedilir.
- Sıfır başarılı/tümü başarısız evaluator sürümlü belgede korunur ve CLI
  compare/report kontrollü biçimde işler.
- Değiştirilmiş accuracy, susceptibility, ECE veya metric coverage değeri,
  completion yenilense bile reddedilir.
- Partial-failure ve tam-success study örneklerinde sayaç denklemleri exact testlidir.
- E4a repeat-scoped parent eşlemesi ve E3 strict publish sınırı korunur.
- Güncel test sayısı collect/run sonuçlarıyla doğru raporlanır; hedefli ve tam
  offline paket, ruff/format/mypy geçer.

## Teslim

Kanıt dizini `docs/reviews/issue-05/E4b-r1/` olmalıdır. README, commands.jsonl,
başlangıç/bitiş hashleri, gerçek diff ve test/kalite loglarının yanında
`revision-map.md` ve güncellenmiş `analysis-version-contract.md` teslim edilmelidir.
Worker çıktıları sonradan düzenlenmeden inceleme kanıtı olarak saklanacaktır.
