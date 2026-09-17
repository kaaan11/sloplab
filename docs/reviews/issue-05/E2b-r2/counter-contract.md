# E2b-r2 — Sayaç sözleşmesi (counter-contract.md)

E2b-r1 sözleşmesi devralındı; iki nokta sıkılaştı (aşağıda ★). Birimler aynı:
`evaluations_attempted = successful + failed`; `adapter_attempts` mantıksal;
`physical_dispatches` gerçekten başlayan transport; ayrı reservation sayacı
yoktur.

## Exact sayaç geçişleri (olay başına)

- Rezervasyon: `physical_dispatches += 1` (cap doluysa artış yok,
  `BudgetExhausted`).
- Pre-dispatch deadline kapısı (outer kontrol): artış yok, `DeadlineExceeded`.
- Transport başladı (success/timeout/429/diğer): sayaçta kalır; timeout ayrıca
  `timeouts += 1`, hepsi `errors += 1` (429 dahil — tel üzerinden geldi).
- ★ Inner pre-dispatch reddi (`BudgetExhausted`/`DeadlineExceeded`, transport
  başlamadı): `physical_dispatches -= 1` (iade); `errors`/`timeouts` değişmez.
  Deadline'ın iki saat okuması arasında bitmesi bu yoldur; contract yarışı
  istisna saymaz (deterministic fake-clock testiyle kapsanır).
- Pacing/`Retry-After` reddi (rezervasyonun üstünde): hiçbir sayaç değişmez.

## Yol denklemleri (korunur)

- Success-after-retry (k timeout + başarı): `evaluations=1`,
  `attempts=k+1`, `physical=k+1`.
- Permanent failure: `evaluations=1`, `attempts=max+1`, `physical=max+1`,
  `failed(timeout)`.
- Cap-in-retry (cap=C): `attempts=C+1`, `physical=C`, `timeouts=C`,
  `errors=C`, outcome `failed(budget)`. (Ret, rezervasyon kapısından döner;
  iade yolu çalışmaz çünkü artış hiç olmamıştır.)
- ★ Deadline yarışı (outer geçti, HTTP reddetti): `urlopen=0`, `physical=0`,
  `errors=0`, `timeouts=0`; iade edilen rezervasyon cap'i korur (aynı cap ile
  sonraki dispatch başarabilir).
- Pacing-deadline reddi: başlamış plan `failed(deadline)`, `attempts=1`,
  `physical` değişmez; başlamamış planlar `not_run(deadline_exceeded)`.

## Şema notu

Sayaç/wrapper şeması değişmedi (`physical_dispatches`, `errors`, `timeouts`;
manifesto/result anahtarları aynı). Legacy bundle okuma E3'e bırakıldı.
