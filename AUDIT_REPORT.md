# SlopLab V2 - Audit Report & Roadmap

Bu rapor, `sloplab` (v0.2.2+) kod tabanında gerçekleştirilen derinlemesine güvenlik ve mimari denetim bulgularını, teknik analizlerini ve `sloplab_v2` için belirlenen önceliklendirilmiş yol haritasını içerir.

---

## 1. Tespit Edilen Hatalar ve Güvenlik Açıkları

### Faz 1 (P0 - Kritik Güvenlik / Safety Bypass)
1. **URL Authority (Userinfo) SSRF / Regex Bypass Açığı (`policy.py`):**
   - **Konum:** `src/sloplab/safety/policy.py`
   - **Sorun:** `_URL_RE` regex'i URL authority (`user:pass@`) yapısını ayrıştıramamaktadır. Örneğin `http://localhost@attacker.com/payload` girildiğinde regex host olarak `localhost` değerini almakta ve `is_reserved_host` bunu geçerli saymaktadır. Sonuç olarak güvenlik filtresi (`validate_content_safety`) saldırgan adresini onaylamaktadır.
   - **Çözüm:** Standart `urllib.parse.urlsplit` kullanılarak doğru hostname çıkarılmalıdır.

2. **Suffix Karşılaştırması ile Sahte Host Bypass'ı (`policy.py`):**
   - **Konum:** `src/sloplab/safety/policy.py`
   - **Sorun:** `_LOCAL_HOST_SUFFIXES = ("localhost", ".localhost", ".local")` listesinde `"localhost"` kelimesi yer aldığı için `host.endswith("localhost")` kontrolü `evil-localhost`, `notlocalhost`, `attackerlocalhost` gibi saldırgan kontrolündeki alan adlarını da onaylamaktadır.
   - **Çözüm:** Sadece `host == "localhost"` veya `host.endswith(".localhost")` / `host.endswith(".local")` şartı aranmalıdır.

### Faz 2 (P1 - Yüksek / Çalışma Zamanı & Metrik Doğruluğu)
3. **`LlmEvaluator`: `Severity` Enum Parse Mantık Hatası (`adapter.py`):**
   - **Konum:** `src/sloplab/evaluators/llm/adapter.py:177-179`
   - **Sorun:** `Severity` bir `StrEnum` olup değerleri küçük harflidir (`info`, `low`, `medium`...), ancak `Severity.__members__` anahtarları büyük harflidir (`INFO`, `LOW`, `MEDIUM`...). Model küçük harf döndüğünde (`"low" in Severity.__members__ == False`) değer sessizce `Severity.MEDIUM`'a düşmekte, büyük harf döndüğünde ise `Severity("LOW")` `ValueError` fırlatmaktadır.
   - **Çözüm:** `Severity(str(severity).lower())` ile güvenli dönüştürme ve fallback sağlanmalıdır.

4. **`compute_calibration_error`: ECE Son Bin IEEE-754 Mantık Hatası (`metrics.py`):**
   - **Konum:** `src/sloplab/scoring/metrics.py:172-175`
   - **Sorun:** `if b == _CALIBRATION_BINS - 1 and not members:` şartı nedeniyle, eğer son bin aralığında 0.95 gibi bir değer varsa `not members` `False` olmakta ve `confidence == 1.0` olan tüm kayıtlar son bin'e dahil edilmeden kaybolmaktadır.
   - **Çözüm:** Son bin için koşul doğrudan `if b == _CALIBRATION_BINS - 1: lo <= c <= hi` şeklinde olmalıdır.

5. **`load_derived_fixture`: Varsayılan `corpus_root` Derinlik Hatası (`loader.py`):**
   - **Konum:** `src/sloplab/corpus/loader.py:133-135`
   - **Sorun:** Varsayılan kök `case_dir.parent.parent` olarak alınmaktadır. Ancak türetilmiş fixture dizinleri 3 seviye derinlikte olduğundan (`out_root / adversarial / <fixture> / <case_id>`), bu değer `out_root / adversarial` olmakta ve `report.path` ile birleşince `adversarial/adversarial` hatası vermektedir.
   - **Çözüm:** `root = corpus_root if corpus_root is not None else case_dir.parents[2]` yapılmalıdır.

### Faz 3 (P2 - Orta / Heuristik & İzolasyon İyileştirmeleri)
6. **`run_llm_pilot`: R04 Identity Hygiene İhlali ve `case_kind="canonical"` Hardcoding (`pilot.py`):**
   - **Konum:** `src/sloplab/experiments/pilot.py:197-215`
   - **Sorun:** `opaque_case_handle` kullanılmamakta, ham `case_id` ve ham doküman değerlendiriciye iletilmektedir. Ayrıca `case_kind="canonical"` sabit yazılmıştır.
   - **Çözüm:** `run_case` mimarisi pilot içine de taşınmalı, opak handle ve dinamik `case.kind` kullanılmalıdır.

7. **`RulesBaselineEvaluator`: Koşullu İfadelerin Koşulsuz Negasyonu Bastırması (`baseline.py`):**
   - **Konum:** `src/sloplab/evaluators/rules/baseline.py:237-241`
   - **Sorun:** Metinde bir adet koşullu sınır ifadesi olması durumunda tüm koşulsuz ifadeler de yok sayılmakta, `REJECT` olması gereken raporlar `NEEDS_MANUAL_REVIEW` olmaktadır.
   - **Çözüm:** Koşulsuz ve koşullu eşleşmeler bağımsız filtrelenmelidir.

8. **`EvidenceGraphBaselineEvaluator`: Eksik Sınıra Çelişki Atfı ve Çift Rationale Prefix'i (`evidence_graph.py`):**
   - **Konum:** `src/sloplab/evaluators/rules/evidence_graph.py:159, 229, 243`
   - **Sorun:** Sınır bölümü hiç olmadığında `GRAPH_BOUNDARY_CONTRADICTS_CLAIM` kodu üretilmektedir. Rationale alanında ise `evidence-graph-baseline: evidence-graph:` çift prefix'i bulunmaktadır.

9. **`parse_report`: Fenced Code Block Uzunluk Takibi (`parser.py`):**
   - **Konum:** `src/sloplab/corpus/parser.py:51-53`
   - **Sorun:** CommonMark standardına göre 4 backtick ile açılan blok 3 backtick ile kapatılamaz. Açılış uzunluğu takip edilmelidir.

### Faz 4 (P3 - Düşük / Sürüm & Dokümantasyon Senkronizasyonu)
10. **Sanal Ortam ve Sürüm Bütünlüğü:**
    - `pyproject.toml` sürümü `0.3.0` olarak güncellenmeli, dokümantasyonlar ve commit logları senkronize edilmelidir.

---

## 2. Uygulama Yol Haritası (Roadmap)

- [x] **Faz 1 (P0): Güvenlik ve Safety Politikası Düzeltmeleri**
  - [x] 1.1 `find_unsafe_urls` URL Authority ayrıştırma düzeltmesi (`urllib.parse.urlsplit`)
  - [x] 1.2 `is_reserved_host` subdomain/suffix eşleşme düzeltmesi
  - [x] 1.3 `tests/unit/test_corpus.py` kapsamlı güvenlik testleri
- [x] **Faz 2 (P1): Temel Çalışma Zamanı ve Hesaplama Düzeltmeleri**
  - [x] 2.1 `LlmEvaluator._to_result` içinde `Severity` case-insensitive parse
  - [x] 2.2 `compute_calibration_error` son bin sınır düzeltmesi
  - [x] 2.3 `load_derived_fixture` varsayılan kök dizin düzeltmesi
  - [x] 2.4 Birim testleri ile regresyon doğrulaması
- [x] **Faz 3 (P2): Heuristik ve İzolasyon İyileştirmeleri**
  - [x] 3.1 `run_llm_pilot` R04 opak kimlik ve dinamik `case_kind` entegrasyonu
  - [x] 3.2 `RulesBaselineEvaluator` sınır negasyonu eşleşme mantığının ayrılması
  - [x] 3.3 `EvidenceGraphBaselineEvaluator` finding ve rationale temizliği
  - [x] 3.4 `parse_report` code fence uzunluk takibi
- [x] **Faz 4 (P3): Sürüm ve Dokümantasyon Senkronizasyonu**
  - [x] 4.1 Sürüm artırımı (`v0.3.0`) ve pyproject/README senkronizasyonu
  - [x] 4.2 Tam test süiti, linter ve tip denetimi (pytest, ruff, mypy)
  - [x] 4.3 Git commit ve remote push

---

## 3. Gelecek Yol Haritası (Future Roadmap - v0.4.0+)

- [x] **Faz 5 (AI/LLM Security): Indirect Prompt Injection (IPI) & Evaluator Hijacking**
  - [x] 5.1 `sloplab.mutations.operators.injection` modülü (`EvaluatorOverrideInjection`, `MarkdownPolyglotInjection`)
  - [x] 5.2 Saldırı Başarı Oranı (`attack_success_rate` / `ASR`) ve `injection_resistance_rate` (IRR) metrikleri
  - [x] 5.3 Güvenlik açığı raporu context injection varyantları ve regresyon testleri
- [x] **Faz 6 (Performans & Ölçeklenebilirlik): Asenkron & Eşzamanlı (Async/Concurrent) Runner**
  - [x] 6.1 `HttpLLMClient` için async arayüz ve `TokenBucketLimiter` rate limiter
  - [x] 6.2 Pilot ve harness için `--concurrency / -j` işçi havuzu desteği
  - [x] 6.3 Hata toleransı, asenkron timeout ve deterministik sıra koruma testleri
- [x] **Faz 7 (Yeni Mimari): Agentic / Tool-Use Triage Değerlendirici Sözleşmesi**
  - [x] 7.1 `AgenticTriageEvaluator` arayüzü ve mock sandbox araçları (`SearchSourceTree`, `ExecutePoCSandbox`)
  - [x] 7.2 Çok turlu (multi-turn) ReAct döngüsü doğrulama harness'ı
  - [x] 7.3 `compute_agentic_metrics` araç kullanım sıklığı ve trace metrikleri
- [x] **Faz 8 (Gelişmiş Metrikler): Semantik Bozulma & Pertürbasyon Bütçesi**
  - [x] 8.1 Vektör/embedding tabanlı anlamsal mesafe (`cosine_similarity` / `compute_text_perturbation`) ölçümü
  - [x] 8.2 Değerlendirici "Dayanıklılık vs. Pertürbasyon Bütçesi" (`compute_robustness_perturbation_curve`) eğrileri


