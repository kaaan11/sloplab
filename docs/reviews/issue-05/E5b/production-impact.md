# E5b — Üretim etkisi (production-impact.md)

## Metin katmanı

`v1-core` konfigürasyonuyla yeniden üretimde 474 türevden **6 dosya**
değişti (E5a envanterindeki 20 aday satırdan planlayıcının seçtiği
adımlara karşılık gelen 3 vaka):

- `totiming-019/...-02/report.md`: `-   interleaved to cancel drift.`
- `oauthstate-029/...-02/report.md`: `-   code parameter.`
- `saml-019/...-03/report.md`: `-   set to another demo user, ...`
- İlgili 3 `mutation-manifest.yaml`: yalnız eklenen
  `span_model: full-item-v1` + `removed_extra_lines: 1`.

Diff'ler yalnızca `-` satırlardır (ekleme yok); komşu baytlar intact.
Sayaçlar değişmedi (`written 237`, `no_op 43` — profilde yeni no-op
yok). E5a envanteriyle uzlaşma: etkilenen 3 vakanın parentları aday
listesindedir; aday≠etki ilkesi korunur.

## Vaka katmanı

Eski/yeni kayıt kümeleri: 594 satır, aynı kimlikler, **0 karar değişimi**
(iki deterministik evaluator). Seçim birliği aynı (`selection_hash` eşit).

## Metrik katmanı (veri × analiz matrisi)

|  | analiz eski-tanım | analiz yeni-tanım (v1) |
| --- | --- | --- |
| veri eski (E1e kayıtları) | eser: susc `-0.0189` / `0.0068` | yeniden hesap: `0.0` / `0.0` |
| veri yeni (E5b kayıtları) | betik-hesabı: `-0.0189` / `0.0068` (yayımlanmadı) | E5b koşusu: `0.0` / `0.0` |
| llm-pilot (canlı) | çalıştırılmadı | çalıştırılmadı (canlı API gerekir; sunulmuyor) |

- Eski-tanım sütunu formül hatasını veriden bağımsız gösterir (aynı
  sahte değerler iki veride de üretilir); düzeltme veriyi değil tanımı
  değiştirir.
- Yeni-veri × yeni-tanım, eski-veri × yeni-tanımla **birebir aynıdır**:
  kalıntı temizliği bu suitte metriği oynatmadı (karar + güven aynı).
- ECE/drift/accuracy iki eksende de aynıdır.

## Sürüm kimliği

`full-item-v1`: vaka manifestolarında (davranış farklılaşan 3 vaka) ve
defter başlığında. Paket `__version__` değişmedi; eski artefaktlar
yeniden üretilmedi.
