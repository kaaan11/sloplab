# E3b-r1 — Legacy ile kesilmiş yeni yayını ayıran yayın protokolü

Durum: İnceleyici düzeltmesiyle kabul edildi. Kabul kaydı:
[E3b-r1 kabulü ve E3 kapanışı](reviews/issue-05/E3b-r1-acceptance.md). Önkoşul:
[E3b revizyon kararı](reviews/issue-05/E3b-acceptance.md). Ortak kurallar:
[worker teslim protokolü](issue-05-worker-delivery-protocol.md).

## Hedef

E3b'nin materialization defteri, evaluator izolasyonu ve coverage ayrımını
koruyarak, tarihsel legacy paket ile completion öncesinde kesilmiş yeni yayın
arasındaki belirsizliği kaldır. Hiçbir tüketici kesilmiş yeni paketi legacy
yolundan okuyamasın.

## Bloklayıcı karşıörnek

İşaretsiz fakat `manifest.json`, `records.jsonl`, `input-identity.json` ve
`execution-recipe.json` taşıyan yeni-study biçimli dizin için mevcut
`open_result_dir(..., purpose=...)` `"legacy"` döndürüyor. Bu dizin completion
öncesinde kesilmiş gerçek bir yeni yayınla ayırt edilemiyor.

## Yayın sözleşmesi

Yeni study ve pilot yazımı, herhangi bir çıktı değişiminden veya model
dispatch'inden önce kalıcı bir in-progress işareti yayımlamalıdır. Okuyucu bu
işareti completion'dan önce kontrol etmeli ve varken paketi açıklayıcı
`BundleError` ile reddetmelidir.

Başarılı yayın sırası şu garantiyi sağlamalıdır: completion tam ve doğrulanabilir
biçimde yazılır; in-progress işareti en son kaldırılır; ancak bundan sonra paket
`complete` görünür. Completion dosya haritası in-progress ve geçici yayın
dosyalarını veri dosyası saymamalıdır. Eski tamamlanmış dizine yeniden yazımda
eski completion, yeni çalışma boyunca tüketilememelidir.

Tarihsel, in-progress işareti taşımayan E3a-öncesi paketler açık legacy modunda
okunmaya devam etmeli ve yeniden yazılmamalıdır. Dosya adını tek başına yeni
şema kanıtı sayan sezgisel ayrım kullanma.

## Kabul ölçütleri

- Study ve pilot başlangıcında in-progress işareti çıktı değişiminden önce görünür.
- In-progress varken `classify_bundle` incomplete döner; `open_result_dir` ve
  strict reader paketi reddeder.
- Completion yazılmış olsa bile son publish adımı tamamlanmamışsa tüketim reddedilir.
- Başarılı publish sonunda yalnız doğrulanabilir completion görünür; in-progress kalmaz.
- Eski tamamlanmış dizine yeniden yazma yarışı ve completion yazım kesintisi testlidir.
- CLI `compare`, `report`, study/benchmark iç okumaları ve `llm_bench` için bypass
  karşıörnekleri kapanır.
- Tarihsel fixture açık legacy yolunda okunur; tarihsel dosyalar değişmez.
- E3b'nin 21 testi, E3a regresyonları ve tam offline paket geçer; canlı ağ kullanılmaz.

## Teslim

Kanıt dizini `docs/reviews/issue-05/E3b-r1/` olmalıdır. README, komut günlüğü,
başlangıç/bitiş hashleri, diff, test ve kalite logları ile yeni yayın durum
makinesini açıklayan `publish-state-contract.md` teslim edilmelidir. Worker
çıktıları sonradan düzenlenmeden inceleme kanıtı olarak saklanacaktır.
