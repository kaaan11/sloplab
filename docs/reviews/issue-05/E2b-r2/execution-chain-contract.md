# E2b-r2 — Yürütme zinciri sözleşmesi (execution-chain-contract.md)

## Tek zincir

Pilot yürütme sınırı tektir: `run_llm_pilot` ve `scripts/llm_bench.py` aynı
kurucuyu kullanır — `sloplab.experiments.pilot.build_pilot_client_chain`:

```text
LlmEvaluator → ThrottledClient → CountingClient → transport
      (pacing/Retry-After)   (tek bütçe sahibi)
```

Kurucu girdileri config değerleridir (`min_interval_ms`, `max_requests`);
`sleep_cap_s` yalnız pacing test hook'udur (üretim `None`). Deadline,
pilot tarafından zincirin dış ucuna kurulur ve içe iletilir
(`ThrottledClient → CountingClient → HttpLLMClient`).

## Sahiplik

- Pacing sahibi: `ThrottledClient` (en fazla bir tane; sayacın üstünde).
- Bütçe sahibi: `CountingClient` (tam bir tane; transportun hemen üstünde).
- `run_llm_pilot`, değerlendiricinin zincirini dispatch öncesi doğrular veya
  kanonik biçime normalize eder (`_normalize_pilot_chain`). Config pacing /
  deadline / cap değerleri wrapper'lardan ayrışamaz.

## Normalize / ret tablosu (dispatch öncesi, sessiz bypass yok)

| Gelen zincir | Sonuç |
| --- | --- |
| `Throttled(Counting(t))`, pacing == config | Kabul (olduğu gibi). |
| `Counting(t)` (çıplak) | Normalize: config pacing ile sarılır. |
| Bütçe sahibi yok | `ValueError` (red). |
| Çift `CountingClient` | `ValueError` (red). |
| Çift `ThrottledClient` | `ValueError` (red). |
| Yanlış sıra (`Counting(Throttled(t))` vb.) | `ValueError` (red). |
| Yabancı wrapper | `ValueError` (red). |
| Pacing != config | `ValueError` (red). |

Normalize yalnızca çıplak sahibeye uygulanır ve pilot-yerel kopyaya
bağlanır; çağıranın değerlendiricisi değişmez. Retlerin tamamı herhangi bir
dispatch öncesi gerçekleşir (transport çağrı sayısı 0 kalır).

## Dispatch olay sırası (tek deneme)

1. `ThrottledClient`: pacing beklemesi (deadline'a sığmazsa ret, sayaç yok).
2. `CountingClient`: deadline kapısı (geçmişse artırmadan ret) → rezervasyon.
3. Transport çağrısı başlar = physical dispatch.
4. Transport sonucu:
   - başarı → physical kalır;
   - timeout/429/diğer transport hatası → physical kalır + error (timeout
     ayrıca) sayılır; 429 sonrası `Retry-After` beklemesi (her zaman tam,
     deadline'a sığmazsa ret);
   - inner pre-dispatch `BudgetExhausted`/`DeadlineExceeded` (transport
     başlamadı: deadline iki kontrol arasında bitti dahil) → rezervasyon
     iade edilir; `physical_dispatches`, `errors`, `timeouts` artmaz.
5. Adapter sınıflandırması terminal/retriable ayrımını uygular (değişmedi).

Inner-transport sözleşmesi: `DeadlineExceeded` yalnızca henüz başlamamış
dispatch'i reddetmek için yükseltilir; başlamış çağrının hatası asla bu
türle bildirilmez.
