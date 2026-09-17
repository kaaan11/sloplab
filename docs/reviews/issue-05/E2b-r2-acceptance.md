# E2b-r2 — İnceleyici düzeltmesiyle kabul ve E2 kapanışı

Tarih: 2026-09-10. **E2b-r2, ana inceleyici düzeltmesinden sonra kabul edildi. E2 kapatıldı.**

## Karar ve doğrulanan davranış

E2b-r2 önceki iki revizyonun bloklayıcılarını kapattı. Pilot ve script ortak
`build_pilot_client_chain` kurucusunu kullanıyor; bare client doğrudan pilotta
config pacing'iyle normalize ediliyor. Yanlış sıralı, çift budget owner,
owner'sız, yabancı veya pacing'i config'ten ayrışan zincir dispatch öncesi
reddediliyor.

Deadline'ın Counting ve HTTP kontrolleri arasında dolduğu karşıörnekte inner
pre-dispatch ret rezervasyonu geri veriyor: `urlopen=0`,
`physical_dispatches=0`, `errors=0`. Retry, cap-in-retry, pacing deadline,
`Retry-After` ve HTTP remaining-time timeout yolları ayrı exact sayaçlarla testli.
Production `Retry-After` sessizce kısaltılmıyor; bütün testler fake transport,
sahte saat veya yamalı `urlopen` kullanıyor.

Worker kanıtında 141 hedefli ve 279 tam offline test, ruff/format/mypy ve
deterministik karşılaştırma exit 0'dır. Ana inceleyici yeni execution-chain
testlerini ve ilgili E2 kümelerini yeniden çalıştırdı, worker run envanterini doğru
kökte 482/482 doğruladı ve iki eski karşıörneği kod üzerinden yeniden sınadı.

## İnceleyici düzeltmesi

Zincir doğrulaması pacing değerini config'e bağlıyor, fakat daha sıkı bir
`CountingClient.max_requests` değeri doğrudan pilotta geçerli olabiliyordu.
Uygulama bunu güvenli biçimde `min(config cap, client cap)` olarak kullanmasına
rağmen manifest yalnız config bütçesini yazdığı için uygulanan fiziksel cap
provenance'da görünmüyordu.

Mevcut daha sıkı client-cap davranışı korundu; manifestoya
`effective_max_requests` eklendi. Regression testi config cap 180/client cap 4
durumunda uygulanan değerin 4 olarak kaydedildiğini doğruluyor. Worker'ın
`docs/reviews/issue-05/E2b-r2/` diff/hash/logları değiştirilmedi ve inceleyici
düzeltmesi öncesindeki teslimi tanımlar.

Son kodla 66 ilgili test ve **tam offline paket 280/280** geçti. İlgili
ruff/format/mypy kontrolleri ve `git diff --check` temizdir. Gerçek ağ veya sleep
kullanılmadı.

Son kodla yeni deterministik review çalışması
`/tmp/sloplab-e2b-r2-review-LQrdBa/run` altında üretildi: 297 vaka, iki evaluator,
594 kayıt. E1e referansına karşı 482/482 dosya kümesi, 480/480 ham veri/identity
dosyası ve suite index eşit; manifestoda yalnız izinli başlangıç/bitiş zamanları
farklıdır. Karşılaştırma `RESULT: OK` verdi. `/tmp` kalıcı arşiv değildir.

## E2 kapanış sınırı

E2a ile failure/karar ayrımı, outcome ledger ve label capability; E2b serisiyle
tek fiziksel bütçe sahibi, retry sınıflandırması, request timeout/toplam deadline,
pacing/`Retry-After`, exact dispatch sayaçları ve tekrar coverage kapısı kapandı.

Bu kabul bundle atomikliği, strict/legacy reader, genel evaluator izolasyonu (E3)
veya metrik formülleri/sürümlü analiz (E4) için kabul değildir. Canlı pilot henüz
başlatılabilir ilan edilmedi. Sıradaki paket [E3a görev dosyasıdır](../../issue-05-E3a-task.md).
