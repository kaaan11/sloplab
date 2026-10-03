# Kanonik korpus canlı LLM çalışması — 28 Eylül 2026

3 Ekim ek kaydı: Dots teşhisi HTTP 400 vermeyi sürdürüyor. Aynı vaka için
ayrı NVIDIA çalışması üç geçerli yanıt verdi; aşağıdaki Dots çalışmasının
59/60 kapsamı değişmedi. [Kapsam tamamlama kaydı](coverage-recovery-2026-10-03.md)
ve [başarısızlıkları koruyan tekrar analizi](variance-analysis.md).

## Kapsam ve kurulum

Kanonik suite sırasındaki 60 farklı vaka, üçer tekrar hedefiyle yedi ayrık
GitHub Actions koşusuna bölündü. İlk [üç vakalık şema kısıtlı
pilot](llm-pilot-structured-2026-09-28.md) ve [on vakalık takip
koşusu](llm-pilot-batch-10-2026-09-28.md) bu yedi koşuya dahildir. Eksik
yanıtlar için iki tek vakalık ek koşu yapıldı. Dokuz artifact'ın tamamı
indirildi, `verify_bundle(..., kind="llm-pilot")` ile doğrulandı ve depodaki
kopyaları ayrıca doğrulandı.

Tüm koşularda model `dots-studio/dots-3-note-preview:free`, prompt SHA-256
`7410aa14ab220e29c92265eae7a6f6bb1efa940b2364365034fbcadf4c1f4d42`,
yanıt şeması SHA-256
`08cddbaf77e328885c16fecabddb5e9d97a4725d4fa7f82f92d0acd82a51dde7`,
`json_schema`/`strict: true`, `provider.require_parameters: true`, sıcaklık `0`
ve temel tohum `20260825` aynıydı. İlk koşu `e20a2b6`, ikinci koşu
`cbb9357`, sonraki koşular `04131677` commit'inde çalıştı. Prompt yalnız
rapor metnini içerir; referans karar modele gönderilmez. Commit'ler ve tüm
çalıştırma ayarları bundle manifestlerinde kayıtlıdır.

| Koşu | Suite indeksi | Vaka × tekrar | Geçerli / planlanan | Fiziksel istek | Not |
|---|---:|---:|---:|---:|---|
| [36437723703](https://github.com/kaaan11/sloplab/actions/runs/36437723703) | 0–2 | 3 × 3 | 9 / 9 | 9 | [Bundle](../experiments/results/llm-pilot/2026-09-28/36437723703/) |
| [36444462899](https://github.com/kaaan11/sloplab/actions/runs/36444462899) | 3–12 | 10 × 3 | 30 / 30 | 30 | [Bundle](../experiments/results/llm-pilot/2026-09-28/36444462899/) |
| [36457213299](https://github.com/kaaan11/sloplab/actions/runs/36457213299) | 13–22 | 10 × 3 | 30 / 30 | 30 | [Bundle](../experiments/results/llm-pilot/2026-09-28/36457213299/) |
| [36458707078](https://github.com/kaaan11/sloplab/actions/runs/36458707078) | 23–32 | 10 × 3 | 30 / 30 | 30 | [Bundle](../experiments/results/llm-pilot/2026-09-28/36458707078/) |
| [36460357015](https://github.com/kaaan11/sloplab/actions/runs/36460357015) | 33–42 | 10 × 3 | 30 / 30 | 30 | [Bundle](../experiments/results/llm-pilot/2026-09-28/36460357015/) |
| [36461933375](https://github.com/kaaan11/sloplab/actions/runs/36461933375) | 43–52 | 10 × 3 | 26 / 30 | 30 | 1 boş yanıt, 3 HTTP 400; [eksik bundle](../experiments/results/llm-pilot/2026-09-28/36461933375/) |
| [36463456436](https://github.com/kaaan11/sloplab/actions/runs/36463456436) | 53–59 | 7 × 3 | 21 / 21 | 21 | [Bundle](../experiments/results/llm-pilot/2026-09-28/36463456436/) |
| [36464461292](https://github.com/kaaan11/sloplab/actions/runs/36464461292) | 47 | 1 × 3 | 3 / 3 | 3 | `saml-019` ek koşusu; [bundle](../experiments/results/llm-pilot/2026-09-28/36464461292/) |
| [36464822213](https://github.com/kaaan11/sloplab/actions/runs/36464822213) | 49 | 1 × 3 | 0 / 3 | 3 | `sqlx-002` ek koşusu; [eksik bundle](../experiments/results/llm-pilot/2026-09-28/36464822213/) |

İlk yedi koşunun seçim aralıkları çakışmıyor ve birlikte 60 vaka kimliğinin
tamamını kapsıyor. İlk koşunun manifestinde `selected_case_ids` alanı henüz
yoktu; üç kimlik outcome kayıtlarından çıkarıldı. Diğerlerinde seçim listesi
manifestte kayıtlı. İki ek koşu bilinçli tekrar olduğu için aralık toplamına
katılmıyor.

## Sonuç ve başarısızlıklar

- Yedi ana koşunun **180 planlı değerlendirmesinin 176'sı geçerliydi**.
  Ek koşularla birlikte **186 fiziksel istek**, **179 geçerli yanıt** ve
  **7 başarısız yanıt** kaydedildi; çalıştırılmamış slot veya timeout yok.
- Ek koşudaki iki yinelenen `saml-019` tekrarını tekilleştirince,
  **180 özgün vaka/tekrar slotunun 177'sinde** geçerli yanıt bulunuyor.
  **59/60 vaka** için en az üç geçerli gözlem var. `canonical-sqlx-002`
  için hiç geçerli gözlem yok.
- Geçerli yanıtların **178/179'u** yazarın referans kararıyla eşleşti.
  Yanıtlanan 59 vakanın **58'i tüm gözlemlerinde oybirliğiyle kararlı**;
  `canonical-saml-019` değişti. Bu 59 vakada ortalama vaka içi güven puanı
  yayılımı `0.0585`. `sqlx-002` için kararlılık hesaplanamaz.
- `canonical-saml-019`un ana koşudaki ilk tekrarı `parse.empty_response`
  ile başarısız oldu; sonraki iki tekrar `accept` verdi. Ek koşudaki üç
  geçerli yanıtın ikisi `accept`, biri `needs_manual_review` dedi.
  Böylece beş geçerli gözlemde **4 `accept`, 1 `needs_manual_review`** var.
- `canonical-sqlx-002` için ana ve ek koşulardaki **6/6 istek HTTP 400**
  döndü. Hepsinin rendered prompt hash'i aynı. HTTP 400'ün sağlayıcı
  tarafındaki açıklaması bundle'da tutulmuyor; nedenini bu kayıtlardan
  belirlemek mümkün değil. Bu yanıtlar karar veya skor sayılmadı.

Altı HTTP 400, manifestlerin `errors` sayaçlarında yer alıyor. Boş yanıt
başarısız bir ayrıştırma sonucu olduğundan bu transport hata sayacına
eklenmiyor. Başarısız iki bundle'ın `stability` alanı, tam başarı kapsamı
bulunmadığı için boş; yukarıdaki 58/59 karşılaştırması tüm geçerli yanıtlar
vaka kimliğine göre birleştirilerek ayrıca hesaplandı. Tekrarlı `saml-019`
yanıtlarının hiçbiri bu karşılaştırmadan atılmadı.

## Yorum sınırı

Korpus [tamamen sentetik, kamuya açık ve model yardımıyla
yazılmıştır](dataset-card.md). Referans kararlar korpusu hazırlayan kişi
tarafından tanımlandı. Bu nedenle 178/179 uyum, bağımsız güvenlik triage
doğruluğu ya da görülmemiş vakalarda performans ölçüsü değildir. Modelin
eğitimde bu yayımlanmış içeriği görüp görmediği bilinmiyor. Bu çalışma tek
modeli, tek günü ve yalnız kanonik vakaları kapsıyor; mutasyonlu vakalar ve
erişim kontrollü taze bir test kümesi değerlendirilmedi. Eksik `sqlx-002`
vakası nedeniyle **60 vaka için tam canlı sonuç** iddia edilmiyor.
