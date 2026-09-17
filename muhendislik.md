# SlopLab — Mühendislik İncelemesi (Çözümü Zor Darboğazlar)

- **Tarih:** 2026-09-09
- **Kapsam:** `src/sloplab/*`, `tests/*`, `benchmarks/*`, `scripts/llm_bench.py`, `docs/*`
- **Sürüm:** `pyproject.toml` + `src/sloplab/__init__.py` = `0.2.2`, branch `main` (`origin/main`'den 2 ahead)
- **Yöntem:** Sadece okuma. Bu dosya dışında projede hiçbir değişiklik yapılmadı.
- **Niyet:** Bug listesi değil; çözmesi mühendislik olarak pahalı / araştırmasız çözülemeyen darboğazlar + verimsiz pattern'ler + araştırma önerileri.

> Özet hüküm: İskelet doğru — deklaratif `MutationSpec`, SHA-tabanlı tohum, plan→materialize ayrımı, no-op şeffaflığı, R04 opak handle, byte-identity sözleşmesi. Ama **edit katmanı satır-dilimleme + genel regex'e**, **planlama corpus sırasına**, **determinizm tek interpreter sürümüne**, **çalıştırma sıralı tek thread'e**, **skorlama küçük-N + elde kalibre edilmiş eşiklere** emanet. Aşağıdaki 12 darboğazın hiçbiri "bir PR ile biter" türünden değil.

---

## A. Çözümü Zor Darboğazlar (madde madde)

### 1. Markdown edit katmanı AST'siz: satır dilimleme + genel regex
- **Belirti:** Tüm operatörler `textops.replace_section_body / remove_section` + `ReportDocument.find_sections(pattern)` üzerine kurulu. `textops.py:22-26` (`lines[:start_line]` / `lines[end_line:]`), `textops.py:12-14` (ilk eşleşmeyi al), heading arama `models/report.py:44-47` case-insensitive `search`.
- **Neden zor:** Nested heading (`### References` bloğunu body'ye gömme `mutations/operators/references.py:83`), çift `## Impact`, `~~~` fence, setext heading, `#Impact` (boşluksuz), HTML comment gibi durumlarda konumlar sessizce kayar. `impact.py:150`'deki ara `parse_report` bunun itirafıdır ama stale-location riski yaratır. Parser ` ``` ` **ve** `~~~` tanırken (`corpus/parser.py:14`), `presentation.py:74,152,165` sadece ```` ``` ```` kontrol eder → `~~~` fenced raporda stil operatörü kodu bozabilir.
- **Ek kırılganlık:** `_NUMBERED_STEP_RE = ^\s*\d+[.)]\s+` (`textops.py:9`) sadece `1.` / `1)` yakalar. `-`, `*`, `a)`, `Step 1:` listeleri görünmez → `evidence.py:62` `len(steps)<2` dalına düşüp tek adımlı raporda "tek adım sil" yerine "bölümü yok et" uçurumu oluşur (`evidence.py:73-75`).
- **Araştırma:** `markdown-it-py` / CommonMark AST + kaynak haritalı (sourcemap) edit motoru; 60 fixture üzerinde corpus-driven fuzz; fence/heading varyant matrisi.

### 2. Cross-version determinizm garantisi yok
- **Belirti:** `derive_seed` SHA256 tabanlı (`mutations/base.py:78-81`), `random.Random(plan.seed)` enjekte ediliyor (`mutations/materialize.py:124`). Ama tüm operatörler `rng.randrange / choice` kullanıyor (`references.py:69-75`, `technical.py:71-75`, `evidence.py:63`).
- **Neden zor:** `random.Random.choice/randrange`'in dahili `_randbelow` algoritması sürümler arası stabil garanti vermez. `docs/adding-mutations.md:10-12` "same seed + input => byte-identical" diyor ama interpreter pin'i yok; testler (`tests/unit/test_mutations.py:72-80`) aynı interpreter'da geçiyor.
- **Araştırma:** RNG'yi `hashlib`-tabanlı sayaç moduna taşıma (`seed||counter → SHA256 → int`) veya stabil PRNG pin'i + `generator_version`'a RNG sürümü ekleme. Her operator sonundaki `rng.getrandbits(1)` çağrıları (`evidence.py:77,107`, `impact.py:105,160` vb.) tek kullanımlık RNG'de determinizmi artırmaz, sadece okuyanı yanıltır — kaldırılması veya gerekçelendirilmesi gerekir.

### 3. Planlama corpus-sırasına bağımlı, içerik-adresli değil
- **Belirti:** `_rotation_offset = fixture_index % len(operators)` (`mutations/planner.py:44-46,58-60`), `discover_fixtures` sorted (`corpus/loader.py:176-177`). Korpusa 1 fixture eklenince aynı gruptaki tüm sonraki fixture'ların operatör ataması kayar. `derive_seed` girdisi `base_seed|parent_id|op|variant` (`mutations/base.py:80`) — parent `report.md` değişirse aynı seed farklı anlam taşır; manifestte parent content hash yok (`mutations/materialize.py:53-72`).
- **Neden zor:** Artımlı reprodüksiyon yok, plan hash'i yok. Her corpus güncellemesi benchmark tarihini kırar (R01'de 340→297 kırılması bunun örneği, bkz. `docs/remediation-audit-v0.2.2.md:38-54`).
- **Araştırma:** Consistent-hashing / rendezvous hashing ile operatör atama; plan dosyasına `parent_content_sha256 + policy_hash` damgası; `case_id`'deki `:02d` (`planner.py:41`) 100+ varyantta taşar, şema genişletilmeli.

### 4. Operatör kompozisyonu tanımsız (zincirleme yok)
- **Belirti:** Tüm operatörler kanonik parent'tan tek adım varsayar. `replace_section_body` sonrası location'lar geçersiz; ikinci mutasyon aynı rapora uygulanırsa adım numarası kayması, çift `References` append (`references.py:86` mevcut bloğu kontrol etmez) olur.
- **Neden zor:** Komütatiflik/çakışma matrisi yok; patch-tabanlı zincirleme + her adımda re-parse + idempotent `case_id` şeması gerekir. Mevcut `case_id` sadece `(parent, op, variant)` kodlar, zinciri kodlayamaz.
- **Araştırma:** Mutasyon cebiri (hangi ikililer çakışır, hangi sırayla komütatif), her adımda re-parse eden zincir motoru prototipi.

### 5. Boyut delta kalibrasyonu psikometrik değil, sezgisel
- **Belirti:** `evidence.py:42-45` `-0.6/-0.25`, `impact.py:75-78` `-0.55/-0.3` gibi sayılar; additive + clamp (`mutations/base.py:84-91`); eksik boyut `0.5` keyfi prior (`base.py:89`).
- **Neden zor:** Boyut etkileşimi yok sayılıyor (reproducibility çökünce claim-consistency de çöker). İnsan yargısıyla hizalı mı bilinmiyor; `dimension_mae` (`scoring/metrics.py:183-193`) bu sezgisel sayıları ground truth sanıyor.
- **Araştırma:** Hakemli skorlama çalışması (inter-rater reliability), IRT/Rasch ile delta kestirimi, `GroundTruth.expected_dimensions` dağılımından ampirik prior çıkarma.

### 6. Leksikal → semantik uçurum (rules baseline corpus-frazına overfit)
- **Belirti:** `evaluators/rules/baseline.py:44-144` ~50 kalıp, operatörlerin eklediği cümlelere birebir bağlı. Modülün kendi itirafı `baseline.py:10-12` + uncertainty itirafı `baseline.py:92-96`. Kanıt: `"Undetermined."` tek kelime ıskalaması review accuracy'yi 0.58→0.81 oynatmış (`docs/evaluator-study-v0.2.md:70-75`).
- **Neden zor:** Fabrikasyon/atfedilmiş CVE/üretilmiş API identifier dış doğrulama ister (changelog/manifest/vendor DB). Çevrimdışı benchmark'ta yok; regex eklemek = corpus-frazını ezberlemek. Parafraz (`actively exploited data breach` → `currently abused leak`), başlık rename, 80-karakter koşullu-cümle penceresi (`baseline.py:237-240`), `[:1]` ile ilk-hit kesip cezada `len()` sayma tutarsızlığı (`baseline.py:217,223,260,270` vs `314-316`) hep bu sınıfın semptomu.
- **Araştırma:** Yeni-held-out corpus ile ezber/yetenek ayrımı; cümle-segmentasyonu + entailment'e geçişin determinizm maliyetiyle birlikte değerlendirilmesi. Eşikler (`0.8/0.78/0.45`, `baseline.py:301-373`) ve güven formülleri (`baseline.py:375-380`) elde kalibre; kalibrasyon hatası 0.27-0.30.

### 7. Negatif kontrol ikilemi (evidence-graph)
- **Belirti:** `evaluators/rules/evidence_graph.py:1-24` bilerek kör: presence-semantik içerik-kalite mutasyonlarını göremez. V26 audit: 12/12 mutated pair `edges=4/4` kalmış (`docs/v26-results-audit.md:15-38`); post-fix bile 6/8 degrading family sıfır. Körlük pin testleriyle sabitlenmiş (`tests/unit/test_evidence_graph_families.py:101-114` `decision == baseline`).
- **Neden zor:** Graph'a içerik-duyarlılığı eklemek = sözleşme değişimi; V26 ispat değeri bozulur, tüm pin testleri + study sayıları güncellenir. Leksikal node dedeksiyonu (`_SEVERITY_WORDS` 7 kelime, `_CONSEQUENCE_WORDS` ~20 stem, `_HEDGED_UNRESOLVED` 4 kalıp vs rules'taki 15) her yeni word-form'da ıskalar (ör. `"persisted" vs persists` vakası).
- **Araştırma:** Ya yeni evaluator yaz (graph v2), ya sözleşmeyi bilinçli değiştir. Mevcut sabitler (`MIN_SUPPORT_STEPS=2`, `edges==4 and overall>=0.75`, güven haritası `evidence_graph.py:214-227`) yeniden kalibre edilmeli.

### 8. LLM hattı: determinizm/bütçe/retry üç katmana dağılmış
- **Belirti:** Adapter'da seed/temperature/top_p yok (`evaluators/llm/adapter.py:39-62,263-265`); retry var ama backoff yok — `time.sleep(0)` (`adapter.py:122`); transport + parse hatası aynı sayaçtan yer (`adapter.py:118-121`); bütçe/rate-limit adapter'da yok, sadece pilot path'te (`experiments/pilot.py:29-140`). `HttpLLMClient` tek `urlopen(timeout=...)` (`adapter.py:275`), connect/read ayrımı yok.
- **Neden zor:** Greedy `\{.*\}` (`adapter.py:37`) uzun prose'ta yanlış span yakalar; failed → `NEEDS_MANUAL_REVIEW, confidence=0.0` (`adapter.py:201-222`) stabilite metriğini sistematik yamultur. `effective_cap=min(config, client._max_requests)` (`pilot.py:177`) private field'a erişir; `sleep_cap_s == request_timeout_s` yeniden-kullanımı (`scripts/llm_bench.py:114-117`) iki kavramı birleştirir; `config.max_cases=None` iken `config.max_cases or 0` → worst_case 0 (`llm_bench.py:82-84`) pre-flight'tan kaçar. Canlı 429/timeout/parse karışımı testte yok — `docs/evaluator-study-v0.2.md:3-7` "live LLM NOT executed in V0.2".
- **Araştırma:** Tek-doğruluk-kaynaklı bütçe sayacı, provider seed/temperature passthrough + provenance'a kayıt, parse-fail vs transport-fail ayrımı, `Retry-After` HTTP-date saat-kayması testi.

### 9. Sıralı çalıştırma: paralellik yok, hata izolasyonu tutarsız
- **Belirti:** `scoring/harness.py:164-165` tek liste-komprehenşın; `experiments/study.py:83-89` çift döngü sıralı; `cli/main.py:195-201` aynı; pilot iç içe sıralı + blocking sleep (`experiments/pilot.py:184-221`, `pilot.py:94-99`); bootstrap saf Python 2000×n döngü (`scoring/comparison.py:170-173`); repo genelinde `concurrent|ThreadPool|ProcessPool|asyncio` sıfır eşleşme. `run_case` içinde `try/except` yok (`harness.py:127-148`) — tek evaluator patlaması 297 caselik study'yi sıfırlar; oysa LLM adapter kendi içinde yakalar (`adapter.py:113-124`) → tutarsız.
- **Neden zor:** Byte-identity sözleşmesi (`experiments/study.py:56-58`) sıralı deterministik yazıma dayanıyor. Paralelleştirme dosya sırası, dict sırası, float-to-string, YAML dump sırası riskleri getirir; `harness.py:123` sort + `materialize.py:162` sort + `study.py:91` join sırası yeniden ispat ister.
- **Araştırma:** Deterministik-shard + sıralı-merge havuz prototipi; per-evaluator izolasyon (failed-record şemsiyesi deterministic hatta da); `study.py:104-105` `started/finished` arka arkaya çağrısı gerçek süre ölçmüyor — wall-clock ölçümü manifest'e taşınmalı.

### 10. Küçük-N istatistiği + metrik tanım borcu
- **Belirti:** Corpus 60 dosya / 52 mantıksal rapor (`18 valid + 26 invalid + 16 review`); `invalid` %43 baskın; `review` yargısı öznel (`docs/dataset-card.md:62-66`). Bootstrap sadece accuracy için (`comparison.py:158-179`); FRR/MDR/ECE/susceptibility için CI yok. `paired_win_loss` ham win/loss/tie, McNemar/p-değeri yok (`comparison.py:22-67`). `per_operator/per_class` alt grupları N≈10-14 ile CI'sız raporlanır. `repeat_stability.cases_compared=len(by_case)` union sayar, kesişim şartı yok (`comparison.py:210-232`).
- **Metrik isim çakışması:** `robustness_delta` (drift, düşük iyi) vs `robustness_score` (ağırlıklı özet, yüksek iyi) (`metrics.py:96,196`); `per_class_accuracy["canonical_overall"]` sentetik anahtar (`metrics.py:48-50,242-252`); `PRESENTATION_OPERATORS` hard-coded 2'li (`metrics.py:15`) — yeni presentation operatörü sessizce ölçüm dışı kalır; `over_rejection` valid→review'u saymaz, `false_reassurance` review→accept ile reject→accept'i birleştirir (`metrics.py:61-76`).
- **Neden zor:** Çözüm ya corpus cap'ini zorlar (charter cap 60 dolmuş, `docs/corpus-balance-v0.2.md:5-7`) ya hiyerarşik model ister. ECE 10-bin equal-width keyfi; geçmişte sınır `~0.01` kaydırmış (`tests/regression/test_calibration_binning.py:1-6`). Multi-seed variance CLI ertelenmiş (`docs/backlog.md:9`, D-0008).
- **Araştırma:** FRR/MDR/ECE için bootstrap CI; McNemar/işaret testi; `presentation_susceptibility` genelleştirmesi (kategori-tabanlı, isim-tabanlı değil); review sınıfı için uzlaşma metriği.

### 11. Provenance / raporlama atomikliği eksik
- **Belirti:** `write_run_jsonl / write_records_csv / write_markdown_report / metrics-*.json` doğrudan `open("w")` + yerinde yazar, tmp+rename yok (`reporting/writers.py:15-111`, `cli/main.py:204-206,394-395`). Her evaluator sonrası `metrics-*.json`, en sonda `run.jsonl` (`cli/main.py:195-215`) — ortada çökerse yarı-ham rapor kalır. `benchmark --no-materialize` eski index + yeni kodla koşabilir; `compare` `run.jsonl`'i doğrulamaz (`cli/main.py:278-305,450-468`). `write_records_csv` boyut sütunlarını veriden keşfeder (`writers.py:88-90`) — şema koşudan koşuya değişir. `run_id=datetime.now(UTC)` (`writers.py:57-58`), `started_at=_utcnow()` (`models/run.py:21-22,40`) bayt-aynılığı bozar; testler ilk satırı atlayarak karşılaştırır.
- **Sayaç/bayrak borcu:** `ExperimentProvenance.request/error/timeout_count` study'de hiç doldurulmuyor (`experiments/runner.py:91-93` vs `experiments/study.py:94-106` hep 0); `ProvenanceOptions` + `AnalysisOptions` bayrakları dekoratif (`experiments/config.py:26-36` tanım, kullanım yok; `cli/main.py:375-382` sadece 2 alan kullanır). `suite_hash = sha256(suite-index.jsonl)` corpus içeriğini değil türetilmiş planı hashler; `evaluate` komutu `suite_name="evaluate", base_seed=0` sabitler (`cli/main.py:261-263`) — aynı index farklı provenansla damgalanır.
- **Neden zor:** Gerçek atomik + deterministik log, saat ve hash'in ayrılmasını + crash-safe yazımı + `correct` bayrağı doğrulamasını (`paired_win_loss` ve bootstrap `r.correct`'i okur, elle üretilmiş JSONL zehirleyebilir) gerektirir.
- **Araştırma:** tmp+rename yazım, `records.jsonl` şema-doğrulamalı okuma, provenans saat/hash ayrımı, `corpus_root` çözümleme (`cli/main.py:152-166,219-236` cwd+parents araması) yerine manifest-gömmeli mutlak yol.

### 12. Konfigürasyon üçlemesi + ölü esneklik + doküman-kod senkron riski
- **Belirti:** `base_seed` üç yerde (`v1-core.yaml:8`, `deterministic-study-v0.2.yaml:19`, `smoke.yaml:5`) manuel senkron; `corpus_root` ikilemesi (study kendi `config.suite.corpus_root` ile discovery yapar `experiments/study.py:65`, suite YAML'in `corpus_root`'u yok sayılır, header'a study'ninki yazılır `materialize.py:110`); `EvaluatorSpec.config: dict[str,str]` yanılsaması (`experiments/config.py:23` — `study.py:84` `get_evaluator(spec.name)` config'i geçirmez, sadece hash'e girer `study.py:89`); `LLMPilotConfig.case_selection` tek değerli Literal + redundant validator (`config.py:78-86`); `smoke.yaml`'da `presentation_pair` yok vs `v1-core.yaml`'da var → uncovered-class hatası verebilir (`planner.py:99-110`); `llm-pilot-v0.2.yaml` vs `llm-full-v0.2.yaml` %90 kopya.
- **Doküman:** Sayılar regex'le korunuyor ama 8 testle sınırlı (`tests/regression/test_doc_consistency.py:44-140`); `progress.md:140-151`, `v26-results-audit.md:49-58` sayıları guard dışında; remediation doc'un kendisi eski dokümanların era-specific sayıları sakladığını söyler (`remediation-audit-v0.2.2.md:127-133`) — okuyucu 340 vs 297, 0.824 vs 0.811 arasında kaybolur. Versiyon kayması: tag `v0.3.0` var ama `pyproject.toml` hâlâ `0.2.2`; guard sadece prerelease regex'i kontrol eder (`test_doc_consistency.py:135-140`).
- **Neden zor:** Tek-seed, leksikal baseline, manuel sayı senkronu kök nedenler; borç testle yamalanıyor (`test_remediation_v022.py`, `test_calibration_binning.py`, `test_suite_paths.py`). 2 günde 56 commit (48+8), 6 yan dal duruyor, `backup/llm-pilot` 11 ahead merge'siz.
- **Araştırma:** Tek-kaynaklı config (suite→study referansı, seed miras alma), `EvaluatorSpec.config` ya gerçekten geçirilmeli ya şemadan çıkarılmalı, doc-sayı guard kapsamı genişletilmeli veya era-etiketleme otomatize edilmeli.

---

## B. Verimsiz / Kırılgan Kod Pattern'leri (kanıtlı seçki)

- **Döngü içinde `re.compile`:** `presentation.py:138` her chunk'ta 10 register pattern'ı yeniden derlenir. Doğru örnek `impact.py:44-50` precompile. Tek seferde derlenmeli.
- **Hedge başına tam split `O(10·L)`:** `presentation.py:217-229` 10 hedge × `split_code_fences(text)`; her iterasyonda `text` değişip yeniden split edilir. Tek split + tek geçiş yeterli.
- **Ara `parse_report`:** `impact.py:150` `ScopeExpansion` tüm dokümanı ikinci kez parse eder. Tek parse'tan iki location hesaplanabilir.
- **Ölü `replace("!!",".")`:** `presentation.py:143` `chunk.replace("!",".").replace("!!",".")` — ilk replace sonrası `!!` kalmaz, ikinci no-op; sıra tersi olmalıydı. Ayrıca `..` üretir.
- **Full-text'u ~10 kez tara:** `baseline.py:206-298` fab/scope/inflation/boundary/contradiction/attribution/reference/noise/uncertainty her biri `full` üzerinde ayrı pass. Tek tokenizasyon + tek pass'a indirgenebilir.
- **Section lookup tekrarı:** `baseline.py:184-198` + graph `_section` 4 çağrı (`evidence_graph.py:106,116,129,134`) raporu her seferinde yeniden gezer. Rapor başına 1 parse-cache yok.
- **Greedy JSON:** `_JSON_OBJECT_RE = \{.*\}` (`adapter.py:37`) prose+JSON+prose'ta en-dış span'ı alır; `json.loads` büyük stringde dener, başarısızlık → retry → bütçe yakma. Katı "ONLY JSON" prompt ile prose-tolerans testi (`test_llm_adapter.py:80-83`) çelişir.
- **Mutated raporu her evaluator için yeniden diskten parse:** `run_case` `load_derived_fixture(case.fixture_dir, case.fixture_dir.parents[2])` (`harness.py:135-136`). `parents[2]` sihirli derinlik; `build_cases` zaten `materialized_root` biliyor (`harness.py:107-108`). N×M disk+parse, önbellek yok. Pilot `_document_for` (`pilot.py:143-150,197`) aynı işin kopyası — ikisi ayrışırsa pilot/study farklı document yükler.
- **Çifte corpus discovery:** `study.py:66` + `harness.py:77` 60 fixture'ı iki kez parse eder. `test_llm_pilot.py:62-69` her test committed bundle'dan `build_cases` yapar; `test_doc_consistency.py:28-41` index'i 6 kez parse eder; `test_experiments.py:59-80` iki tam study koşar.
- **Tam `MetricBundle` israfı:** `per_operator/per_class` her grup için FRR'den ECE'ye her şeyi hesaplar (`comparison.py:85-97`). Tek boyutluk kırılım için gereksiz iş.
- **Global registry sessiz overwrite:** `mutations/base.py:62-63` aynı isimle `register` ezer; duplicate koruması yok. Import sırası değişirse farklı operatör kazanır.
- **Stringly-typed no-op sinyali:** `materialize.py:127` `any(k=="note" ...)`. Gelecekte `note` anahtarını başka amaçla kullanan operatör yanlış skip edilir. Kısmi kurtarıcı `materialize.py:131` (`mutated==raw`) ama ikisini de unutmak mümkün.
- **Safety drop'ları izsiz:** `materialize.py:137-140` violation'da `continue` — ne `skipped`'e ne index'e yazılır. Planlanan sayı (`suite.py:68-74` `estimated_case_count`) ile yazılan sayı diverge olur.
- **Provenance çift sarma + eksik diff:** `materialize.py:59` `parameters={"choices": parameters}`; manifestte diff/patch, parent hash, operatör version yok; sadece `generator_version` (`materialize.py:70`). `removed_step_text` gibi tam cümleler manifesta gömülür (`evidence.py:70`) şişirir.
- **`parents[2]` kırılganlığı:** `materialize.py:88-91` relative path `case_dir.parents[2]==out_root` varsayar. Dizin şeması değişirse sessiz yanlış path.
- **Test zayıflıkları:** `tests/unit/test_mutations.py:151` `assert "critical" in ... or True` (tautology); `:118` `assert A and B or C` (öncelik hatası); `:63-64` `len==12` hardcode + `:46-59` elle `ALL_OPS` (yeni operatörde iki yer güncellenmeli); `test_mutation_properties.py:48-51` `title == old or mutated==raw` ikinci disjunct pratikte redundant; CVE uzayı `randrange(10000)` (`references.py:126`, `technical.py:73`) 237 case'de ~%70+ çarpışma; 3-cümle entropi (`references.py:162-168,205-212`) evaluator'ü 3 kalıba overfit eder.
- **Tip disiplini:** `group_by(..., key_fn: Any)` (`comparison.py:75,144`), `_run_evaluators_over_suite(...) -> list[Any]` (`cli/main.py:169-193`), `EvaluationContext.report: Any` (`models/evaluation.py:61`); `planner.py:76-80` `cast(Any, ...)` type-safety'yi deler; `GroundTruth` vs `MutationManifest`'ta `_check_dimensions` kopyası (`models/manifest.py:41-52,109-119`); `validate_corpus(corpus_root)` ölü parametre (`validation.py:121` `_ = corpus_root`).

---

## C. Araştırma Önerileri (öncelik sırasına göre)

1. **AST-tabanlı sourcemap editörü (en yüksek getiri).** `markdown-it-py`/CommonMark + konum-korumalı replace/remove; fence/heading varyant matrisi + corpus fuzz. Başarı ölçütü: 60 fixture × 12 operatörde no-op-oranı ve konum-kayması sıfırlanır, `~~~`/`#Impact`/çift-heading vakaları pin testine girer.
2. **İçerik-hash'li stabil planlama + provenance şeması.** `parent_content_sha256 + policy_hash` damgası, consistent-hashing atama, `case_id` şema genişletmesi, manifestte diff/parent-hash/operatör-version. Başarı ölçütü: 1 fixture eklenince diğer atamalar oynamaz; eski/new plan diff'lenebilir.
3. **Boyut-deltalarının ampirik kalibrasyonu.** Hakemli skorlama + IRT/Rasch; `0.5` prior yerine dağılımdan prior. Başarı ölçütü: inter-rater κ + delta güven aralıkları dokümante edilir.
4. **Deterministik-shard havuz + hata izolasyonu.** Sıralı-merge garantili paralel harness; deterministic hatta failed-record şemsiyesi; tmp+rename yazım. Başarı ölçütü: 297×2 koşuda süre/çekirdek doğrusallığı + byte-identity korunur.
5. **Metrik CI genişletmesi.** FRR/MDR/ECE/susceptibility için bootstrap CI; McNemar; `PRESENTATION_OPERATORS` isim-seti yerine kategori-tabanlı; review-uzlaşma metriği. Başarı ölçütü: per-operator tabloları N ve CI ile raporlanır.
6. **LLM bütçe tek-kaynağı + seed passthrough.** Sayaç birleşimi, `Retry-After` saat-kayması testi, parse-vs-transport retry ayrımı, model/seed/temperature provenance'a. Başarı ölçütü: worst-case pre-flight `None` yolunda da doğru; 429 döngüsü bütçe yakmaz.
7. **Config tek-kaynağı + doc-guard genişletmesi.** Seed/corpus_root mirası, `EvaluatorSpec.config` kararını ver (geçir ya da çıkar), era-etiketli sayı guard'ları, `tag == package` kontrolü. Başarı ölçütü: `smoke.yaml`/`v1-core.yaml` policy setleri senkron testi geçer.

---

## D. Kanıt Endeksi (dosya:satır)

| İddia | Kanıt |
|---|---|
| Tohumda içerik yok, `0.5` prior, sessiz overwrite | `mutations/base.py:62-63,78-91` |
| Rotasyon kayması, `:02d` taşma, ölü `_ = index` | `mutations/planner.py:38-46,60,41,119` |
| `note` sinyali, clone guard, izsiz safety, `parents[2]`, çift sarma | `mutations/materialize.py:59,88-91,119-145,162-175` |
| İlk-match, dar adım regex'i, satır aritmetiği | `mutations/textops.py:9-14,22-42,45-57` |
| Fence uyumsuzluğu parser vs presentation | `corpus/parser.py:14` vs `mutations/operators/presentation.py:57-90,150-172` |
| Döngü-içi compile, hedge re-split, ölü `!!` | `mutations/operators/presentation.py:138,217-229,143` |
| Tek-kelime replace+break, ara re-parse | `mutations/operators/impact.py:96-101,150` |
| 3-cümle entropi, CVE `randrange(10000)`, `or True` testi | `mutations/operators/references.py:162-168,205-212,126` + `tests/unit/test_mutations.py:118,151,63-64` |
| Contract + registry (LLM hariç) + oracle | `evaluators/base.py:12-55` + `evaluators/oracle.py:27-48` |
| Rules sinyal/skor/karar/güven + corpus itirafı | `evaluators/rules/baseline.py:10-12,34-153,300-380` |
| Graph node/edge/karar + negatif kontrol | `evaluators/rules/evidence_graph.py:46-84,103-152,214-227` + `:1-24` |
| LLM greedy JSON, `sleep(0)`, failed record, timeout | `evaluators/llm/adapter.py:37,104-124,201-222,238-279` |
| Counting/Throttled, effective_cap, pre-flight | `experiments/pilot.py:29-54,69-140,177,189-196` + `scripts/llm_bench.py:46-98,111-123` |
| Sıralı harness + `parents[2]` + opak handle | `scoring/harness.py:35-37,127-165` |
| Metrik çekirdek + hard-coded presentation seti + binning | `scoring/metrics.py:15-16,53-152,155-180,196-255` |
| Win/loss, group_by `Any`, bootstrap, stability union | `scoring/comparison.py:48-97,158-179,210-232` |
| Study akışı + sayaçsız provenance + `started==finished` | `experiments/study.py:60-107` + `experiments/runner.py:73-96` |
| Ölü bayraklar (`ProvenanceOptions`, `AnalysisOptions`, `case_selection`) | `experiments/config.py:26-36,78-86` |
| Atomik-olmayan yazım, `run_id` saat, CSV dinamik şema | `reporting/writers.py:15-111` + `models/run.py:21-40` |
| CLI sabit `suite_name/base_seed`, dar `compare` | `cli/main.py:195-215,261-263,278-322,359-382,450-491` |
| Küçük-N, charter cap, review öznelliği | `docs/dataset-card.md:8-16,60-67` + `docs/corpus-balance-v0.2.md:5-18` |
| R01 pop kırılması, V26 kök neden, kalibrasyon kayması | `docs/remediation-audit-v0.2.2.md:24-54` + `docs/v26-results-audit.md:15-58` + `tests/regression/test_calibration_binning.py:1-6` |

---

## E. Kapsam Dışı Notlar

- Güvenlik incelemesi yapılmadı (bu dosya mühendislik incelemesidir; `safety/policy.py` sadece evaluator-sızıntısı bağlamında anıldı).
- Bilimsel/metodolojik geçerlilik (construct validity, dış geçerlilik) ayrı bir `derin-arastirma` çalışması gerektirir — burada sadece mühendislikten görünen istatistiksel güç ve kalibrasyon borçlarına değinildi.
- Canlı LLM koşusu yapılmadı; LLM bulguları kod + test + runbook okumasına dayanır (`docs/evaluator-study-v0.2.md:3-7` "live LLM NOT executed").
