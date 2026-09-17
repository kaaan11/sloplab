# SlopLab — Bilimsel / Araştırma İncelemesi (Düşmanca İnceleme)

- **Tarih:** 2026-09-09
- **Kapsam:** `docs/methodology.md`, `docs/dataset-card.md`, `docs/evaluator-study*.md`, `docs/decision-log.md`, `docs/reproducibility.md`, `src/sloplab/scoring/*`, `src/sloplab/evaluators/*`, `src/sloplab/mutations/*`, `src/sloplab/experiments/*`, `benchmarks/*` + `muhendislik.md` (başlangıç hipotezi olarak kullanıldı)
- **Sürüm:** paket `0.2.2`, `base_seed 20260825`, popülasyon **297 vaka (60 canonical + 237 derived)**, 52 ebeveyn, tek seed, canlı LLM koşulmadı (D-0013)
- **Yöntem:** Bu dosya dışında projede değişiklik yapılmadı. Hipotezlerimiz sadece başlangıç noktası olarak kullanıldı; çerçeve sorgulandı.
- **Duruş (kelimesi kelimesine):**
> Do not optimize this project. Try to falsify the need for the project first.

## Merdiven hükmü (peşin, üç promptun özeti)

```
1. Novel değilse — göster.
2. Novel ise — construct'u çökertmeye çalış.
3. Construct ayakta kalırsa — measurement'ı çökert.
4. Measurement ayakta kalırsa — causal identification'ı çökert.
5. O da kalırsa — statistics/power'ı çökert.
6. Hepsi ayakta kalırsa — ANCAK O ZAMAN geliştirme öner.
Kural: Stop at the first rung that breaks.
```

- **Prompt1 (Novelty + construct): Basamak 2'de DURDU.** Yöntem-novelty zayıf-geçer (dar alan-instantiation), construct kırık: `triage robustness` ölçülebilir tanımlı değil, 5 boyut lexical aritmetik, `review` ground truth maintainer judgment, rules tek kelimeyle 0.23 oynuyor.
- **Prompt2 (Measurement + identification, KOŞULLU): Basamak 3'te DURDU.** Construct onarılsa bile alet fraz-varlığını ölçüyor (verbatim şablon↔regex eşleşmesi), `expected_*` tek-yazarlı, kontroller zarfı kapatıp mektubu açık bırakıyor, drift ebeveyn-referanslı.
- **Prompt3 (Statistics + scoring + repro + external, KOŞULLU): Basamak 5'te DURDU.** Construct+measurement onarılsa bile güç yok (etkin N≈52, per-family 10-14, susceptibility n=39), skorlama gerekçesiz (40/25/15/10/10, ECE 10-bin, dar over-rejection), repro dar (tek makine, tag-paket uyumsuz), dış geçerlilik kanıtsız (English-only, sentetik, canlı model yok).
- **Sonuç:** Geliştirme önerisi yok (merdiven yasağı). Aşağıdaki `Redesign/Cost` alanları onarım maliyetini belgelemek içindir, optimizasyon tavsiyesi değildir.

> Proje çalışıyor olabilir ama doğru işi yaptığı kanıtlı değil. Aşağıdaki sayılar (`0.811`, `0.802`, `88 vs 8`) ampirik sinyal olarak kullanıldı, sonuç olarak değil.

---

## 0. Başlangıç hipotezlerimiz ve çerçeve sorgusu

Başlangıç çerçevemiz (`docs/methodology.md:9-11`): *"Benchmark results answer exactly one question: how robust is a given evaluator's triage behavior on this corpus, under these mutations?"* + kapsam kilidi D-0001 (offline, sentetik, network'süz) + D-0002 (expected explicit) + D-0012 (V0.2 discrimination mission).

Çerçeve sorgusu — bu sorunun kendisi sorunlu:

1. **"Robustness" kimin robustness'ı?** Human triyajörün mü, otomasyonun mu, human-AI takımının mı? Dokümanda özne yok. Gerçek triyaj dedup + repro + müşteri bağlamı + SLA + ödeme politikasıdır; SlopLab tek-rapor tek-karar ölçer.
2. **"Correct triage" kime göre doğru?** `valid→accept, invalid→reject, review→needs_manual_review` (`docs/methodology.md:17-19`) + derived `expected_decision` manifestte explicit (D-0002). Ama review sınıfı *"maintainer judgment, reasonable people could disagree"* (`docs/dataset-card.md:64-65`). κ yok, adjudication yok, kör ikinci yargıcı yok.
3. **Degrading/neutral ayrımı nedensel mi?** `docs/methodology.md:25-35` ayrımı yapar ama ayrımı yazanla operatörü yazanla baseline'ı yazan aynı kimlik (`git log` 56/56 tek yazar — Prompt2 VERIFIED). D-0012 "12 operatör frozen, label adjustment yok" hatayı kilitler, denetlemez.
4. **`docs/methodology.md:107` kuralı ihlal ediliyor:** *"Group derived cases under their parents; never count variants as independent"* — ama accuracy paydası 297, MDR 96, bootstrap iid (`scoring/comparison.py:168-173`). Normatif cümle ile operatif kod çelişiyor.
5. **Kapsam cümlesi dürüst ama yetersiz:** "this corpus, under these mutations" daraltması tanımsız construct'u tanımlı yapmaz. Raporun geri kalanı ("triage evaluators", "benchmark", "robustness", 0.811 tablosu) genel okunur.

---

## 1. Novelty + construct validity (Prompt1 — Basamak 2 KIRIK)

### Soru 1.1: Bu iş gerçekten yeni mi?

| Alan | İçerik |
|---|---|
| Closest prior work | CheckList (Ribeiro vd., ACL 2020, MFT/INV/DIR); AdvGLUE (Wang vd., NeurIPS 2021, 14 attack); LLMBar (Zeng vd., ICLR 2024, 419 pair Natural+Adversarial, polished-but-wrong); HELM (Liang vd., 2022, accuracy/calibration/robustness/fairness + perturbation); PIT/Major mutation testing (Jia & Harman 2011); MT-Bench/Chatbot Arena (Zheng vd., 2023, position/verbosity/self-enhancement bias) |
| Evidence (VERIFIED) | İddia `docs/methodology.md:9-11` + `README.md:11-16,34-36`. Operasyon: 60 fixture (`docs/dataset-card.md:8-14`: 18 valid/10 invalid/16 review/8 pair=16 dosya), 12 operatör frozen (D-0012 `docs/decision-log.md:104-113`), 297 vaka (`benchmarks/suites/v1-core.yaml:3-8`), seed 20260825. Sayılar rules 0.811/MDR 0.802, graph 0.542 (`docs/evaluator-study-v0.2.md:22-32`). Canlı LLM yok (`docs/evaluator-study-v0.2.md:3-7`, D-0013) |
| Contradiction | CheckList INV/DIR ↔ degrading/neutral ayrımının atasıdır. AdvGLUE "%90 attack invalid, human filtre şart" dersini verdi; SlopLab'da filtre yok, maintainer judgment var. LLMBar polished-but-wrong + zayıf judge chance-level sonucunu üretti; `presentation_susceptibility` (`scoring/metrics.py:124-152`) bunun daraltılmış tekrarıdır. HELM multi-metrik+perturbation'ı standartlaştırdı. PIT kodu mutate eder, SlopLab input'u mutate eder — isim akrabalığı, mekanizma değil |
| Threat | Yöntem-novelty çöker. Kalan aday "triage domaini" ama gerçek triyaj (repro, dedup, business-context severity: Bugcrowd VRT, CVSS, HackerOne/Intigriti workflow) D-0001 ile bilinçli dışlanmış. Arada kalan "sentetik prose'a 12 regex-edit" ne genel-robustness'a genellenir ne gerçek-triyaja transfer olur |
| Kill criterion | (a) LLMBar-Adversarial veya CheckList DIR/INV ile aynı sıralama (rules > structure-only) daha büyük N + insan-uzlaşmalı GT ile üretilirse; (b) ayırt edicilik (88 vs 8, graph 6/8 family sıfır) sadece lexical-rules vs by-design-kör-graph kurmaca farkı çıkarsa. (b) itiraflı: graph *"intentionally blind … demonstrate that SlopLab detects such blindness"* — keşif değil tautology |
| Redesign | Domain-transfer ispatı: lisanslı scrubbed gerçek bounty raporlarında 12 operatörün ekolojik karşılığı var mı? D-0001'i deler |
| Cost | Yüksek: PII scrub + lisans + triajör uzlaşması; cap 60 dolu, corpus büyümeden yapılamaz |
| When required | `future-study` |

### Soru 1.2: Construct ölçülebilir mi?

| Alan | İçerik |
|---|---|
| Closest prior work | Cronbach-Meehl nomological network; IRT/Rasch; HELM scenario×metric taksonomisi; BIG-bench (204 task) capability disiplini; LLM-judge bias taksonomisi (Zheng 2023; CALM 12-bias) |
| Evidence (VERIFIED) | Construct dağınık: `README.md:9,34-36`, `docs/methodology.md:9-11`. Operasyonel yük: 3 karar + 5 boyut (`docs/methodology.md:72-77`) + 8 metrik (`scoring/metrics.py:30-46`). Deltalar sezgisel (`-0.6/-0.25`, additive+clamp `mutations/base.py:84-91`, eksik `0.5` prior). Review GT öznel (`docs/dataset-card.md:64-65`) |
| Contradiction | Boyutsallık, karar↔boyut nedensel harita, human-korelasyon tanımsız. 5 boyut lexical aritmetik (`rules/baseline.py:300-343`, `evidence_graph.py:192-209`). İtiraf: *"sensitive to exact phrases operators insert"* (`baseline.py:10-12`), uncertainty overlap (`baseline.py:92-96`). Sinyal: `"Undetermined."` ıskalaması review accuracy 0.58→0.81 (`docs/evaluator-study-v0.2.md:70-75`) — 0.23 fraz-ezber kanıtı |
| Threat | Tüm metrikler anlamsızlaşır: neyin %80'i? "Bu corpus'un bu frazlarına bu threshold'larla uyan bayrakların" %80'i. Review'u κ'sız "doğru" saymak skor değil kanaat |
| Kill criterion | Kör mini-çalışma: 2-3 bağımsız triajör 16 review + 10 invalid'i skorlasın. Review κ<0.6 veya 5 boyutun human-korelasyonu lexical-baseline korelasyonundan ayırt edilemezse construct yoktur |
| Redesign | (i) Triyajı daralt (sadece gözlemlenebilir reproducibility/presence, boyutları at) veya (ii) human-uzlaşma + IRT kalibrasyon. İkisi de frozen-12 kilidine dokunur |
| Cost | Orta-yüksek: hakemli skorlama + κ + IRT; mevcut `dimension_mae` çöpe çıkar |
| When required | `pre-evaluation` — canlı LLM pilotundan ÖNCE zorunlu |

### Soru 1.3: Construct ↔ operasyonel tanım boşluğu

| Alan | İçerik |
|---|---|
| Closest prior work | LLMBar Natural vs Adversarial; CALM attack-and-detect; AdvGLUE human-filtre; Bugcrowd VRT P1-P5 / CVSS (severity = exploitability × business-context) |
| Evidence (VERIFIED) | `metrics.py:61-76` (FRR birleştirir, over-rejection dar), `:79-94` (MDR payda 96), `:96-122` (drift parent-referanslı, payda 141), `:124-152` (susceptibility 2 isim `metrics.py:15`, payda 39), `:155-180` (ECE 10-bin). R01 340→297 (`docs/remediation-audit-v0.2.2.md:38-54`). Graph 12/96 = 11 contradict + 1 borderline, 6 family sıfır by-design (`docs/evaluator-study-v0.2.md:42-48`) |
| Contradiction | Over-rejection valid→review'u saymaz; FRR review→accept ile reject→accept'i birleştirir — en pahalı hatalar karışır. Susceptibility isim-setine bağlı, n=39 anekdot. Drift parent kararı yanlışsa "stabil" görünür — consistency = correctness sanılır. Graph sıfırı "başarısızlık" değil tasarım; MDR'yi yetenek diye okumak tautology. `dimension_mae` kendi kuyruğunu kovalar (beklenen = operatörün yazdığı delta) |
| Threat | R01'de 43 clone çıkınca accuracy 0.824→0.811, FRR 0.088→0.094, susceptibility -0.031→-0.019 oynadı — sayılar mutasyon kalitesine değil no-op sayımına duyarlı. Tek seed, per-family N≈10-14, FRR/MDR/ECE CI yok — "discrimination mission" (D-0012) kanıtlanamaz, iki el-yapımı oyuncağın kurmaca farkı sergilenir |
| Kill criterion | Parafraz-testi: operatör cümlelerini anlam-koruyan parafrazla değiştir. Rules MDR 0.802'den çökerse ölçülen "degradation" değil "fraz-ezber"dir. Maliyetsiz, pre-QC'de yapılabilir |
| Redesign | Held-out corpus + parafraz-invariance + kategori-tabanlı susceptibility. Frozen-12 + 60-cap'i kırar |
| Cost | Orta: yeni fixture + safety-validasyon + tüm study regenerasyonu (tarih kırılır) |
| When required | `pre-QC` — geçmeden QC verilemez (ama önce construct onarılmalı) |

---

## 2. Measurement + identification + controls (Prompt2 — Basamak 3 KIRIK, koşullu)

### Soru 2.1: Alet construct'ı mı ölçüyor?

| Alan | İçerik |
|---|---|
| Closest prior work | Gururangan 2018 / Poliak 2018 / McCoy 2019 (annotation artifacts, hypothesis-only, lexical overlap); Geirhos 2020 (shortcut/Clever Hans); Campbell/Goodhart |
| Evidence (VERIFIED) | Şablon↔regex birebir: `impact.py:32-39` → `baseline.py:65-74` (3/3), scope 2/2, misattribution 3/3, invention 3/3. Uzunluk-confound: kanonik ~1508 char; `add_irrelevant_detail` 1885 (+377), `fabricate_reference` 1776 (+268) — metrik metin okumaz (`metrics.py:3-5`). Presence-only: edge'ler varlık sayar (`evidence_graph.py:143-150`, `MIN_SUPPORT_STEPS=2`), V26 "12/12 edges=4/4" itirafı. Overlap itirafı `methodology.md:124-128` |
| Contradiction | Alet davranış sağlamlığı değil şablon aşinalığı + uzunluk + başlık-uyumu ölçer. `professionalize_language` substance'a dokunmaz ama preambül ekler; `add_irrelevant_detail` sadece başlık ekler → `TANGENTIAL/INFO + noise_penalty=0.02` (`baseline.py:147-149,281-289,358`) — "noise tolerance" değil "başlık regex toleransı" |
| Threat | Ortak-neden konfound'u: bağımsız değişken (semantik bozulma) ile sinyal (regex hit/uzunluk) karışık. Operatör cümlesi değişse skor 0.23 oynar çünkü skor cümleye endeksli |
| Kill criterion | (a) Parafrazda MDR >0.15 düşüş; (b) length-matched kontrolde etkinin yarısı kayboluyorsa; (c) yeni corpus'ta review-accuracy şansa düşüyorsa. (a) kod-eşleşmesiyle kanıtlı |
| Redesign | Holdout paraphrase havuzu (baseline yazarının görmediği ekip), length/section-matched kollar, maintainer-dışı kör doğrulama. 12 operatör + 50 kalıp birlikte gider |
| Cost | Yüksek: yeniden yazım + kör etiket (60×3 + 237×2) + havuz altyapısı; tek yazarla imkânsız |
| When required | `pre-QC` — geçmeden tek "robustness" sayısı yayımlanamaz |

### Soru 2.2: `expected_decision` authorship

| Alan | İçerik |
|---|---|
| Closest prior work | Rosenthal expectancy; NIH rigor (bağımsız adjudication); Geiger 2020 crowdwork; Northcutt confident learning |
| Evidence (VERIFIED) | Tek yazar 56/56. Kaynak `MutationSpec.decision_by_parent_class` (`mutations/base.py:30-41`): ör. `evidence.py:46` VALID→REVIEW, `references.py:158` VALID→REJECT, `confidence_overstatement` mapping yok → daima nötr. Ama `confidence_overstatement` CALIBRATION -0.2/CONSISTENCY -0.25 degrade eder, `remove_affected_version` SCOPE -0.35 degrade eder — 141 nötr vakanın içi degrading dolu; doğru davranan (REVIEW'a çeken) yanlış sayılır (perverse incentive). `0.5` üç anlamlı (prior + oracle fallback `oracle.py:35-36` + LLM-fail `adapter.py:212-218`). Kanonik boyutlar iki-ondalık sezgisel (ör. `authz-001/manifest.yaml:19-24`). Denetim yok; D-0012 dondurması hatayı kilitler; `"never adjust labels"` (`methodology.md:112`) mekanizmasız |
| Contradiction | D-0002 gerekçesi ("auditable, not buried in code") ile gerçek çelişir: politika manifestte ama manifesti üreten kod aynı yazarın. Denetlenebilirlik ≠ geçerlilik. Reviewer da aynı kişi (`threat-model.md:25`) |
| Threat | Confirmation bias + expectancy: sınavı hazırlayan + cevabı yazan + baseline'ı sınava ayarlayan aynı ekip (0.58→0.81 artışı itiraflı corpus-adjacent) |
| Kill criterion | Kör yeniden-etiketleme: operatör adını görmeyen 2 bağımsız yargıcı 96+141 vakayı etiketlesin. κ<0.6 veya flip >%15 ise payda geçersiz. Şu an κ tanımsız → varsayılan hüküm geçersiz (NIH rigor) |
| Redesign | Yazar-ayrılığı (operatör ≠ etiket ≠ baseline), kör adjudication, vaka-bazlı insan kararı |
| Cost | Yüksek: dış yargıcı + adjudication + 12 mapping çöp; tek-yazarlı projede organizasyonel karşılanamaz |
| When required | `pre-QC` — κ raporlanmadan MDR/accuracy'den cümle kurulamaz |

### Soru 2.3: Kontroller neyi kaçırıyor?

| Alan | İçerik |
|---|---|
| Closest prior work | Placebo/no-op; blinding (Schulz & Grimes); demand characteristics (Orne); stilometri sızıntısı (Mosteller & Wallace); shortcut leakage (Wang, Clark) |
| Evidence (VERIFIED) | R04 sadece id/path gizler (`harness.py:35-37,140-147`); metin açık, şablon verbatim. Test zarfı denetler (`test_remediation_v022.py:313-317`), metni değil. Label-independence tek sentetik gövdede (`test_rules_baseline.py:143-147`). R01 43 clone attı, kalan hedge'li alt-popülasyon (seçim yanlılığı); susceptibility 68→39. Drift çocuk→ebeveyn kararı (`metrics.py:96-121`); Prompt3 düzeltmesi: 8 `pair-b` (polished) hiç ebeveyn değil — drift hep `plain` ebeveyne bakıyor (tasarım yanlılığı, VERIFIED). Sıra-randomizasyonu yok (`harness.py:164-165`, protokolde sıra maddesi yok). LLM fail→REVIEW (`adapter.py:201-222`) review-accuracy şişirir; decoding belirtilmemiş |
| Contradiction | `threat-model.md:22-24` "leak tests assert" — zarfı denetler. Degrading/nötr "kontrol" gibi sunulur ama ayrım denetimsiz — kontrol, kontrol-edilmeyeni kontrol ediyor |
| Threat | (i) Operatör metinden okunur → MDR şişer; (ii) drift ebeveyn-hatayı ödüllendirir; (iii) R01 popülasyonu seçer. Nedensel okuma ("mutasyon → robustness eksikliği") bozulur |
| Kill criterion | (a) Kör metin-sınıflandırıcı operatörü >%30 tahmin ediyorsa (12 sınıfta) R04 ölü — verbatim nedeniyle önceden ölü. (b) Ebeveyn-doğru alt-kümede drift ≠ 0.007 ise metrik tanımsız. (c) Sıra-randomize koşuda flip > CI ise sıra kontrolsüz |
| Redesign | Paraphrase-normalize + length/section-match, beklenen-referanslı drift, R01 duyarlılık analizi, sıra-randomizasyonu + fail-ayrı-raporlama |
| Cost | Orta-yüksek: metrik tanımı + metodoloji yeniden yazılır, tarih kırılır |
| When required | `pre-evaluation` — (a)+(b) olmadan koşulan her vaka sızıntılı |

### Soru 2.4: Nedensel mi korelasyonel mi? + Soru 2.5: Hans/Goodhart/judge-bias

- **Randomizasyon yok:** tek seed reprodüksiyondur, randomizasyon değil (`v1-core.yaml:8`, `deterministic-study-v0.2.yaml:19`). Atama `fixture_index % len` (`planner.py:44-46,58-60`) — propensity tanımsız, overlap yok, SUTVA ihlali (52 ebeveyn, dağılım `{7:14,4:11,3:10,1:8,5:5,8:4}`). `methodology.md:107` "bağımsız sayma" der ama paydalar bağımsız sayar; bootstrap iid (`comparison.py:168-173`). m≈4.6-5.7, ρ≈0.2'de Deff≈1.7 — CI geçersiz. **Kill:** ebeveyn-içi permütasyon null-dağılımı veya cluster-bootstrap CI iid-CI'dan genişse iddia ölür. **When:** cluster-bootstrap `pre-evaluation`, blok-randomize multi-seed `future-study`. Nedensel kelimesi yasak.
- **Hans:** verbatim eşleşme + V26 + 0.58→0.81 corpus-adjacent ayar. **Goodhart:** ~50 kalıp public; MDR = regex eklemek; `threat-model.md:25` kalıp-eklemeyi yasaklamaz. **Judge-bias:** prompt tek-sıralı, length-normalizasyon yok, decoding kilitsiz, pilot sıfır gözlem (D-0013). **Kill:** naif-regex katılımcısı MDR'yi >0.1 artırıyorsa ölçü gamedir (mekanik olarak ölü); pozisyon-swap susceptibility işaretini değiştiriyorsa LLM iddiası ölür (zaten boş küme). **When:** `future-study` (holdout + gaming-testi + counterbalance olmadan leaderboard yasak; pilot koşmadan LLM cümlesi yasak).

---

## 3. Statistics + scoring + repro + external (Prompt3 — Basamak 5 KIRIK, koşullu)

### Soru 3.1: Güç — 297 mi, 52 mi?

- **Nüfus:** 60 dosya/52 lojik, 297=60+237, küme `[1×8,3×8,4×12,5×4,7×16,8×4]` (VERIFIED hesap), m≈5.7/4.95. MDR 96 (family 10-14), susceptibility 39 (48+5'ten non-accept), drift 141. Cap 60 dolu.
- **Çelişki:** 297 "n" gibi kullanılır (CI 0.768-0.855 `evaluator-study-v0.2.md:36-37`, 88 vs 8). Bootstrap iid (`comparison.py:168-173`). ICC=0.2'de DEFF≈1.94→Neff≈153; ICC=0.5'te Neff≈88. Bildirilen genişlik 0.087, gerçek 0.12-0.17 olmalı.
- **Per-family güç yok:** `0/12` Wilson [0.00,0.24], `11/11` [0.74,1.00], `9/13` [0.42,0.87], `4/5` [0.38,0.96] — "sıfır" ile "şans" ayırt edilemez. Susceptibility -0.019 SE≈0.10, sıfırı kapsar. Drift 1/141 Wilson [0.001,0.039] — "yok" ile "40×" aynı veriyle uyumlu. FRR/MDR/ECE/susceptibility CI yok; `per_operator/per_class` CI'sız; `repeat_stability` union sayar (`comparison.py:219`).
- **Kill:** cluster-bootstrap CI iid'den ≥%30 genişse veya per-family genişlik >0.40 (hepsi öyle) veya susceptibility CI sıfırı kapsıyorsa (kapsıyor) güç iddiası ölür — üçü de ölü.
- **Redesign/Cost/When:** Birim = ebeveyn (N=52); cluster-bootstrap + hiyerarşik model + exact CI zorunlu (1 gün/1 hafta); n≥30/family için corpus 60→200+ charter + PII hattı = aylar. Mevcut CI'lar geri çekilmeden sayı alıntılanmamalı.

### Soru 3.2: Skorlama şeması varsayımları

- **Kanıt:** ağırlık 40/25/15/10/10 + reweight (`metrics.py:196-216`, `methodology.md:86-94`); ECE 10-bin equal-width (`metrics.py:16,155-180`); over-rejection sadece valid→reject (`metrics.py:70-76`); FRR birleştirir (`:61-67`); presentation 2 isim (`metrics.py:15`); `robustness_delta` (düşük iyi) vs `robustness_score` (yüksek iyi) + sentetik `canonical_overall` + eşikler/güven (`baseline.py:359-380`).
- **Çelişki:** "Auxiliary" etiketi kurtarmaz — ağırlık gerekçesiz, reweight karşılaştırmayı bozar (farklı paydaların 0.8393'ü). ECE dağılımı dejenere (rules `0.45×77,0.50×69,0.60×66,0.852×62` + kuyruk), çoğu bin boş; geçmişte sınır 0.01 kaydırmış. `over_rejection=0.000` artefakt (valid→review sayılmıyor — rules'un ana davranışı!). Eşikler elde kalibre; güven kalibre değil (ECE 0.30) ama skora %10 giriyor. `PRESENTATION_OPERATORS` yeni operatörü dışlar; `writers.py:142-143` label'ı ters.
- **Kill:** ağırlık ±10'da sıralama değişiyorsa veya ECE 10→15'te sıralama (0.298 vs 0.270) dönüyorsa veya valid→review dahil edilince 0.000 çöküyorsa şema ölür (üçüncüsü tanım gereği ölü).
- **Redesign/Cost/When:** skoru kaldır veya maliyet-kalibre et (gerçek triyaj maliyeti bilinmiyor); ECE equal-mass + diyagram + CI; over-rejection `valid→¬accept`, FRR'yi ayır; kategori-tabanlı presentation; `decision_drift_rate` rename. Skor düzelmeden `0.8393 vs 0.4465` kullanılmamalı.

### Soru 3.3: Tekrarlanabilirlik — byte-identity neyi kapsamaz?

- **Kanıt:** iddia "across runs and machines" (`reproducibility.md:3-4`, `study.py:56-58`) ama istisnalar: ilk satır timestamp hariç (`writers.py:57-58`, `models/run.py:21-22,40`), manifest saatleri hariç (`study.py:104-105` started==finished), `final-audit.md:50-51` "single-machine … cross-platform not asserted" itirafı. Ortam `>=3.11 validated 3.14`, yorumlayıcı pin yok; `random.Random` sürüm-garantisiz. R01 340→297 tarih kırılması canlı örnek; planlama corpus-sırasına bağımlı. Tag `v0.3.0` vs paket `0.2.2` uyumsuz (VERIFIED). Yazım atomik değil; `correct` doğrulanmadan skorlanır (`comparison.py:50-51,172`); sayaçlar hep 0 (`study.py:94-106` vs `runner.py:91-93`); `suite_hash` planı hashler corpus'u değil; `evaluate` sabit damgalar (`cli/main.py:261-263`).
- **Kill:** farklı minor Python/OS'te hash tutmazsa veya tag-paket uyumsuzken atıf yapılırsa veya 1 fixture eklenince eski sayılarla karşılaştırılabiliyorsa iddia ölür (ikincisi şu an ölü).
- **Redesign/Cost/When:** iddiayı daralt (CPython 3.14/Linux/commit/seed), pin + hashlib-sayaç RNG + parent/policy hash + tmp+rename + şemalı okuma + tag==package guard. "Across machines" ya kanıtlanmalı ya silinmeli (makale öncesi); tag uyumsuzluğu hemen.

### Soru 3.4: Dış geçerlilik — hangi popülasyona?

- **Kanıt:** English-only, tam sentetik, 6 fictional app, CVE-2099, example.org (`dataset-card.md:20-42,62-66`); review maintainer judgment; canlı LLM yok (D-0013); severity sandbox `impact_class` (CVSS/VRT eşlemesiz `models/enums.py:54-60`); kapsam "this corpus, under these mutations" (`methodology.md:7-11`).
- **Tehditler:** (a) Base-rate: corpus invalid %43 (`corpus-balance-v0.2.md:11-15`), gerçek prevalans farklı → FRR 0.094'ün PPV'si çöker. (b) Severity prose değil: exploitability×business-context yok. (c) Süreç yok: dedup/repro/SLA/kuyruk/Human-AI deferral modellenmemiş (ECE 0.30 ile politika kurulamaz). (d) Dil: Türkçe ek-fiil/hedge lexical'ı kırar, test yok. (e) Canlı model yok: iki kural sistemi farkı LLM hakkında bir şey söylemez.
- **Kill:** sanitize gerçek örneklemde veya ikinci-yazar corpus'ta sıralama korunmuyorsa veya Türkçe pilotta rules çöküyorsa veya prevalans-duyarlılık FRR yorumunu tersine çeviriyorsa genelleme ölür (şu an iddia kurulmamalı — pozitif kanıt yok).
- **Redesign/Cost/When:** held-out yazar + sanitize gerçek pilot (lisans/PII — `backlog.md:6-8`) + CVSS/VRT + deferral-maliyetli teaming + Türkçe mini-corpus. Ölçek mevcut projeyi aşar. Dürüst ad: *"English synthetic prose-consistency probe"*. Kapsam cümlesi tüm alıntılarda zorunlu.

---

## 4. Bizim düşünmediğimiz teoriler (bu incelemede getirilenler)

1. **Annotation artifacts / hypothesis-only (Gururangan/Poliak/McCoy):** skor şablon ezberi olabilir; hipotez-sadece baseline (rapor metni olmadan operatör tahmini) şart.
2. **Shortcut learning / Clever Hans (Geirhos/Lapuschkin/Pfungst):** model doğru cevabı yanlış nedenden verir; `"Undetermined."` 0.23 sıçraması Hans kanıtı.
3. **Goodhart/Campbell/Strathern:** hedef olan ölçü bozulur; ~50 public kalıp + MDR leaderboard = regex ekleme oyunu. `threat-model.md:25-27` sadece skoru değil kalıbı da kapsamalı.
4. **Experimenter expectancy (Rosenthal/Bemis-Lehman):** tek yazar = hem sınav hem cevap; kör adjudication şart (NIH rigor).
5. **Base-rate neglect (Kahneman-Tversky):** %43 invalid tabanında FRR gerçekte çalışmaz; prevalans-duyarlılık eğrisi şart.
6. **Severity sosyolojisi (CVSS/FIRST, Bugcrowd VRT):** severity prose-etiketi değil bağlamsal karardır; impact-inflation yakalamak stil-polisliği olabilir.
7. **Sosyoteknik triyaj (Wonnemann/Almeida etnografileri):** dedup/repro/müşteri/SLA olmadan "triage benchmark" eksik construct.
8. **Human-AI teaming (Bansal/Lai):** deferral kuyruk maliyeti + güven kalibrasyonu olmadan REVIEW sayısı anlamsız.
9. **Cluster-RCT / DEFF (Donner-Klar/Kish) + Rubin/Neyman:** 297 iid değil 52 küme; randomization inference + ICC + design effect şart.
10. **Calibration patolojisi (Guo/Nixon):** equal-width ECE boş-bin toplamıdır; equal-mass + diyagram şart.
11. **Scoring-değer-yargısı (Hand/Jacobs):** 40/25/15/10/10 ahlaki/operasyonel maliyettir, teknik sabit değil; karar-teorik gerekçe şart.
12. **Reproducibility krizi (Stodden/ACM badging/Popper):** re-execution ≠ replication; byte-identity daraltılmalı.
13. **Benchmark yanılsaması (Bender-Koller):** "triage" adı genel yetenek çağrıştırır; ad dürüstleşmeli.
14. **Negatif-kontrol tautology:** kör tasarlanan kontrolün kör çıkması başarı değil tanımdır; pin-testleri falsifiye edilemezlik yaratır.
15. **Publication bias / researcher DF (Ioannidis/Orben):** 2 baseline + tek seed + era-karışık sayılar (`evaluator-study.md:52-60` eski 340'lı sayılar guard dışında); pre-kayıt şart.

---

## 5. Yanlış varsayımlarımız (açık liste)

1. `n=297 bağımsız gözlem` — yanlış; birim 52 ebeveyn (8 pair-b hiç ebeveyn değil). VERIFIED.
2. `Bootstrap CI geçerli` — yanlış; iid küme-yapıyı ihlal eder, sadece accuracy'de var. VERIFIED.
3. `Per-family N≈10-14 yeterli` — yanlış; Wilson genişlikleri 0.25-0.60. VERIFIED.
4. `Susceptibility n=39 anlamlı` — yanlış; 5/39 vs 5/34 gürültü (SE≈0.10). VERIFIED.
5. `Drift 0.007 stabilite` — yanlış; tek olay, Wilson [0.001,0.039]. VERIFIED.
6. `88 vs 8 üstünlük` — yanıltıcı; 201 tie + el-ayarlı baselinelar, McNemar bile genellemez. VERIFIED.
7. `Ağırlıklar doğal` — gerekçesiz; reweight karşılaştırmayı bozar. VERIFIED.
8. `ECE 10-bin tarafsız` — keyfi; dağılım dejenere, 0.01 kaymış. VERIFIED.
9. `over_rejection=0.000` — tanım-artefaktı; valid→review sayılmıyor. VERIFIED.
10. `Byte-identical = tam repro` — dar; timestamp/manifest hariç, tek-makine, pinsiz, tag uyumsuz (`v0.3.0` vs `0.2.2`). VERIFIED.
11. `Sonuçlar triyaja genellenir` — kanıtsız; English/sentetik/fictional/CVE-2099/LLM-yok/CVSS-yok/teaming-yok. VERIFIED (eksiklik); transfer-büyüklüğü HYPOTHESIS.
12. Prompt2'deki `"25 drift ebeveyni yanlış"` sayısal iddiası — bu haliyle doğrulanamadı (Prompt3 kayıt-hesabı parent lookup'ların bulunduğunu gösterdi). Gerçek sorun daha sinsi: 8 polished ebeveyn hiç kullanılmıyor + metrik ebeveyn-kararına sirküler bağımlı. **Açık araştırma borcu olarak işaretlendi** (bkz. §6.7).

---

## 6. Detaylı incelenmesi gereken noktalar (araştırma önerileri — zaman etiketli)

| # | Soru | Kill/karar eşiği | Maliyet | When |
|---|---|---|---|---|
| 6.1 | Review κ + 5 boyut human-korelasyonu (2-3 kör triajör, 16 review + 10 invalid) | κ<0.6 veya human-korelasyon lexical-korelasyondan ayırt edilemezse construct yok | Orta-yüksek | `pre-evaluation` (pilot öncesi zorunlu) |
| 6.2 | Parafraz-invariance (operatör cümleleri anlam-koruyan parafraz; başlık rename) | MDR >0.15 düşerse alet fraz-ezberi; benchmark kendi cümlelerini ölçüyor | Düşük-orta (kod + küçük corpus) | `pre-QC` |
| 6.3 | Kör yeniden-etiketleme (2 bağımsız yargıcı, 96+141 vaka, κ + flip) | κ<0.6 veya flip >%15 ise payda geçersiz (şu an κ tanımsız → geçersiz) | Yüksek (dış yargıcı) | `pre-QC` |
| 6.4 | Metin-sızıntı sınıflandırıcısı (id yok, sadece metin → 12 operatör; >%30 = sızıntı) + length-matched kontrol | Sızıntı + uzunluk-etkisi yarıyı açıklıyorsa MDR/FAR geri çekilir | Orta | `pre-evaluation` |
| 6.5 | Ebeveyn-doğru alt-küme drift + beklenen-referanslı drift tanımı | Alt-küme drift ≠ 0.007 ise mevcut drift tanımsız | Düşük (mevcut kayıt) | `pre-evaluation` |
| 6.6 | Cluster-bootstrap + hiyerarşik model + per-family Wilson/Clopper-Pearson + güç analizi (n≥30/family mi?) | CI ≥%30 genişlerse veya genişlik >0.40 veya susceptibility CI sıfırı kapsarsa (kapsıyor) güç iddiası ölür | 1 gün / 1 hafta / aylar (corpus) | Hemen (CI geri çekme) + `future-study` (corpus) |
| 6.7 | Drift-ebeveyn tutarsızlığını çözümle (Prompt2 vs Prompt3 çelişkisi: 25 yanlış-ebeveyn iddiası vs lookup-bulundu + 8 pair-b ebeveyn-dışı bulgusu) | Kayıt-seviyesi audit: hangi 141 vakanın ebeveyni hangi canonical, ebeveyn kararları ne, pair-b neden ebeveyn değil | Düşük (1-2 gün kayıt audit'i) | `pre-QC` (sayılar dondurulmadan önce) |
| 6.8 | Skor duyarlılığı (ağırlık ±10, ECE 10→15/equal-mass, valid→review dahil over-rejection) | Sıralama/yorum değişiyorsa şema ölür (üçüncüsü ölü) | Günler | Skor kullanılmadan önce |
| 6.9 | Cross-platform repro (3.11 vs 3.14, Linux farkı, tag==package guard, RNG migration) | Hash tutmazsa "machines" iddiası silinir; tag uyumsuzluğu hemen giderilir | Saatler/günler/1-2 hafta | Makale öncesi + hemen (tag) |
| 6.10 | Transfer: held-out yazar corpus + prevalans-duyarlılık + (opsiyonel) sanitize gerçek pilot + Türkçe mini-corpus + CVSS eşleme | Sıralama korunmuyorsa genelleme ölür | Haftalar/aylar | Dış-genelleme cümlesinden önce |
| 6.11 | Gaming-testi (naif-regex katılımcısı MDR +0.1?) + holdout-operatör ayrımı + pre-kayıtlı analiz | Gameable ise leaderboard yasak; holdout olmadan "discrimination kanıtlandı" tekrarlanmamalı | Orta-yüksek | `future-study` + hemen (eski sayılar `evaluator-study.md:52-60` güncellenmeli/silinmeli) |
| 6.12 | LLM kolu: decoding-kilidi + pozisyon-counterbalance + length-stratifikasyon + fail-ayrı-raporlama + ≥3 repeat pilot | Pilot koşmadan LLM cümlesi yasak (şu an durum doğru: kurulmamış) | Pilot bütçesi (60×3×model) | Pilot koşmadan önce protokol şart |

---

## 7. Prior art (kararı taşıyanlar — güven ayrımıyla)

- Ribeiro vd., *Beyond Accuracy: CheckList*, ACL 2020 (`arXiv:2005.04118`) — güven YÜKSEK. INV/DIR ↔ degrading/neutral atası.
- Wang vd., *AdvGLUE*, NeurIPS 2021 (`arXiv:2111.02840`) — YÜKSEK. "%90 invalid, human filtre şart" negatif sonucu.
- Zeng vd., *LLMBar*, ICLR 2024 (`arXiv:2310.07641`) — YÜKSEK. Polished-but-wrong, zayıf judge chance-level.
- Zheng vd., *MT-Bench/Chatbot Arena*, NeurIPS 2023 (`arXiv:2306.05685`) — YÜKSEK/ORTA. Position/verbosity/self-enhancement.
- Liang vd., *HELM*, 2022 (`arXiv:2211.09110`) — YÜKSEK/ORTA. Multi-metrik + perturbation + calibration standardı.
- Srivastava vd., *BIG-bench*, 2022 (`arXiv:2206.04615`) — YÜKSEK/DÜŞÜK-ORTA (genişlik argümanı).
- Gururangan 2018 / Poliak 2018 / McCoy 2019 / Geirhos 2020 / Lapuschkin 2019 — YÜKSEK (artifact/shortcut/Hans).
- Efron 1979 bootstrap; Wilson 1927; Kish 1965 DEFF; Donner & Klar cluster; Liang & Zeger 1986; Ioannidis 2005; Dodge multi-seed; Guo 2017 / Nixon 2019 calibration; Hand classifier-metrics; Campbell/Goodhart; Kahneman-Tversky base-rate; FIRST CVSS; Bansal/Lai teaming — YÜKSEK/ORTA.
- Jia & Harman 2011 mutation survey; PIT; Shi 2025 position-bias; CALM 2025; HackerOne/Intigriti/YesWeHack triage docs — ORTA, **UNVERIFIED-CITATION** (tam-metin çekilmedi, özet-seviyesi; kararın dayanağı yapılmadı).

## 8. Uncertainty handling (VERIFIED vs HYPOTHESIS)

- **VERIFIED (dosya:satır + hesap):** kapsam cümlesi; 60/52/297/96/141/39 sayıları; seed tekliği; canlı-LLM yokluğu; maintainer-judgment; corpus-fraz itirafları; graph negative-control + 6 family sıfır; metrik tanımları/paydalar/eşikler/ağırlıklar; verbatim şablon↔regex eşleşmeleri; uzunluk ortalamaları; tek-yazar 56/56; R01 340→297 + CI etkileri; 0.58→0.81 sıçraması; R04'ün zarfı denetlediği; fail→REVIEW; iid-bootstrap kodu; union-stability; timestamp-hariç diff; single-machine itirafı; sayaçların 0 kalması; tag `v0.3.0` vs paket `0.2.2`; Wilson CI hesapları; küme-dağılımı; 8 pair-b ebeveyn-dışılığı; eski-sayı era-karışıklığı.
- **HYPOTHESIS (ölçülmedi, kill için gerekli değil):** parafraz düşüş büyüklüğü (yön VERIFIED, miktar değil); ICC ρ ve gerçek DEFF (m VERIFIED, ρ değil — ama DEFF>1 garantidir); kör κ değeri (yokluk VERIFIED, değer değil); LLM sıra-etkisi; gerçek prevalans/transfer katsayısı/Türkçe düşüşü (yön belli: dışarıda düşer); cross-version RNG kırılması (gözlenmedi, dokümantasyon riski).
- **Kural:** HYPOTHESIS hiçbir kill'in dayanağı yapılmadı; kill'ler mekanik gerçeklere dayanır. HYPOTHESIS sadece şiddet belirsizliğidir, hükmü değiştirmez.
- **Açık çelişki:** §5 madde 12'deki drift-ebeveyn sayısı Prompt2 ile Prompt3 arasında tutarsızdır — §6.7'de pre-QC audit borcu olarak işaretlendi, karar dayanağı yapılmadı.

---

## 9. Kapsam dışı

- Güvenlik incelemesi yapılmadı (mühendislik dosyasında da yapılmadı).
- Mühendislik verimsizlikleri burada tekrarlanmadı — bkz. `muhendislik.md` (12 darboğaz + pattern kataloğu + kanıt endeksi).
- Canlı LLM koşusu yapılmadı; LLM bulguları kod + test + runbook okumasına dayanır.
- Bu dosya optimizasyon reçetesi değildir. Merdiven yasağı gereği geliştirme önerilmedi; §6'daki tablo öldürme/karar eşikleri tablosudur.

**Kapanış (düşmanca, dürüst):** Construct cilalansa bile eldeki düzenek kendi cümlesini kendi regex'iyle bulan, uzunluğu kontrol etmeyen, cevabı yazıp denetletmeyen, ebeveyn-hatayı ödüllendiren, tek-tohumlu, kümeyi yok sayan, LLM'i koşmamış bir sistemdir. Mevcut haliyle dürüst iddia en fazla şudur: *"İngilizce sentetik prose-tutarlılık probu, tek corpus, CI'sız, genelleme-yok."* Bunun üstündeki her cümle için §6'daki kill-testleri şarttır.
