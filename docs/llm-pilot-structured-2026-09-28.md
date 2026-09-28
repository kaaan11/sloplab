# Şema kısıtlı canlı LLM pilotu — 28 Eylül 2026

## Kurulum ve model seçimi

İlk [pilot kaydında](llm-pilot-2026-09-28.md) kullanılan modelin 18 yanıtından
üçü katı JSON doğrulamasını geçmedi. Takip çalışmasında istekler `json_schema`
biçiminde, `strict: true`, `provider.require_parameters: true` ve sıcaklık
`0` ile gönderildi. Yerel ayrıştırıcı yanıtları ayrıca doğrulamaya devam etti;
ham model yanıtları kaydedilmedi.

Şema destekleyen `nvidia/nemotron-3-super-120b-a12b:free` ile yerel 3 × 3
denemesinde 8/9 yanıt geçerliydi; bir yanıt `parse.empty_response` oldu.
`dots-studio/dots-3-note-preview:free` ile yerel deneme 9/9 geçti. Yerel deneme
sırasında checkout güncellendiği için o bundle'ın commit alanı başlangıç anını
yansıtmıyor; aşağıdaki GitHub koşusu sabit checkout üzerinde yapıldı ve
arşivlenen kanıt odur. Sonraki koşular için commit kimliği ilk istekten önce
sabitlenecek şekilde pilot kodu da düzeltildi.

## Doğrulanmış GitHub koşusu

- [Workflow koşusu 36437723703](https://github.com/kaaan11/sloplab/actions/runs/36437723703):
  `main` commit `e20a2b6be2e4d44c044c11264994140ca7422ea9`, üç kanonik vaka ×
  üç tekrar, `dots-studio/dots-3-note-preview:free`.
- Planlanan 9 değerlendirmeden **9'u başarılı**; başarısız veya çalıştırılmamış
  değerlendirme yok. **9 fiziksel istek**, sıfır transport hatası ve sıfır
  timeout. İş süresi 4 dakika 8 saniye.
- Manifestte `output_mode: json_schema`, `temperature: 0.0`,
  `provider_require_parameters: true`, çözümlenmiş model kimliği ve
  `response_schema_sha256: 08cddbaf77e328885c16fecabddb5e9d97a4725d4fa7f82f92d0acd82a51dde7`
  kayıtlı. Prompt hash'i ilk pilotla aynı:
  `7410aa14ab220e29c92265eae7a6f6bb1efa940b2364365034fbcadf4c1f4d42`.
- İndirilen ve depoya kopyalanan [bundle](../experiments/results/llm-pilot/2026-09-28/36437723703/)
  `verify_bundle(..., kind="llm-pilot")` ile iki kez doğrulandı: artifact indirildiğinde
  ve arşiv kopyası oluşturulduğunda. `completion.json` içerik hash'lerini kapsıyor.

| Vaka | Üç tekrardaki karar |
|---|---|
| `canonical-authz-001` | `accept` |
| `canonical-authz2-014` | `accept` |
| `canonical-cachehdr-024` | `needs_manual_review` |

Manifestte kapsam `9/9`, oybirliği `3/3`, karar değişimi `0` ve ortalama güven
puanı yayılımı `0.05` olarak hesaplandı. Bunlar yalnız bu üç kanonik vaka ve bu koşu
için geçerlidir; modelin genel doğruluğunu veya gelecekteki servis
kararlılığını göstermez. Daha geniş çalışma, 60 × 3 planının yeniden denemelerle
540 istek gerektirmesi ve 180 istek sınırını aşması nedeniyle daha küçük,
ayrı bütçelenmiş dispatch'lere bölünmelidir.
