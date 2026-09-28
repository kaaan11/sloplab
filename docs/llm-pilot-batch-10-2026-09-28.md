# On yeni vakalık canlı LLM pilotu — 28 Eylül 2026

## Kapsam ve kanıt

Önceki [üç vakalık şema kısıtlı pilotun](llm-pilot-structured-2026-09-28.md)
ardından, kanonik suite sırasındaki 3–12 indeksleri seçildi. Böylece önceki üç
vaka yeniden değerlendirilmedi. [GitHub koşusu
36444462899](https://github.com/kaaan11/sloplab/actions/runs/36444462899)
`main` commit `cbb9357949b31f7be8e2f95fcf797ef0bb74523b` üzerinde
`case_offset=3`, `max_cases=10`, `repeats=3` ile çalıştı.

Model `dots-studio/dots-3-note-preview:free`; prompt hash'i, yanıt şeması
hash'i, sıcaklık ve şema zorlaması önceki başarılı koşuyla aynı. Planın en kötü
durum istek sayısı, iki yeniden deneme dahil 90; gerçek kullanım **30 fiziksel
istek** oldu. İş **14 dakika 21 saniyede** tamamlandı.

İndirilen [bundle](../experiments/results/llm-pilot/2026-09-28/36444462899/)
ve arşiv kopyası `verify_bundle(..., kind="llm-pilot")` ile doğrulandı. Manifestte
seçilen on vaka kimliği, offset, model ve istek ayarları kayıtlı. Önceki koşunun
outcome kayıtlarıyla karşılaştırıldığında vaka kümeleri ayrık; model, prompt,
şema ve örnekleme ayarları eşit.

## Sonuç

- **30/30 başarılı değerlendirme**; başarısız veya çalıştırılmamış kayıt,
  transport hatası ve timeout yok.
- **10/10 vaka oybirliğiyle kararlı**, karar değişimi sıfır. Ortalama vaka içi
  güven puanı yayılımı `0.1`.
- Normalize kayıtlardaki kararlar, bu kanonik örneğin referans kararlarıyla
  **30/30** eşleşti. Üç tekrarda her vakanın kararı aynı olduğu için vaka
  düzeyinde eşleşme **10/10**.

| Karar | Vakalar |
|---|---|
| `accept` | `canonical-csvinj-017`, `canonical-ghauthz-015` |
| `reject` | `canonical-corswild-025`, `canonical-dup-007` |
| `needs_manual_review` | `canonical-cachepois-027`, `canonical-crypto-011`, `canonical-cspnonc-021`, `canonical-deserial-030`, `canonical-filetype-023`, `canonical-graphql-028` |

İki ayrık başarılı koşuda toplam **13 kanonik vaka × 3 tekrar = 39/39 geçerli
değerlendirme** elde edildi; 13 vakanın tümünde kararlar tekrarlar boyunca aynı
ve referans kararlarla uyumlu. Bu, suite sırasındaki ilk 13 vakaya ait gözlemdir.
Kalan 47 kanonik vaka ve mutasyonlu vakalar değerlendirilmedi; bu örnek genel
triage doğruluğu veya gelecekteki servis kararlılığı için yeterli değildir.
