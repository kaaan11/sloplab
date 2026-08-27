# SlopLab Release Notes - v0.4.0

**Release Date:** 2026-08-28  
**Codename:** *Adversarial Injection & Agentic Triage*

SlopLab v0.4.0, zafiyet raporu önceliklendirme ve triyaj modellerinin (LLM & Heuristic Evaluators) güvenliğini ve dayanıklılığını test eden en kapsamlı güncellemedir. Bu sürümle birlikte platform, salt kural ve retorik manipülasyonunun ötesine geçerek **yapay zeka güvenliği (AI Security), prompt injection direnci ve otonom araç kullanan (agentic) değerlendiriciler** için bir endüstri standardı benchmark haline getirilmiştir.

---

## 1. Yeni Özellikler ve Mimari Geliştirmeler

### 1.1 Indirect Prompt Injection (IPI) & Evaluator Hijacking
- **`EvaluatorOverrideInjection`:** Zafiyet raporlarının kritik bölümlerine (özellikle adımlar ve güvenlik sınırları) sistem talimatlarını çiğnemeye yönelik doğrudan IPI payload'ları enjekte eder.
- **`MarkdownPolyglotInjection`:** HTML yorumları (`<!-- ... -->`) ve gizli CSS markup'ları içine parser'ları aldatıcı gizli saldırı vektörleri yerleştirir.
- **Yeni Güvenlik Metrikleri:**
  - `attack_success_rate` (ASR): Enjeksiyonun modeli aldatarak geçersiz bir raporu zorla `ACCEPT` kararına götürme oranı.
  - `injection_resistance_rate` (IRR): Modelin prompt injection saldırısına karşı gösterdiği direnç (`1.0 - ASR`).

### 1.2 Asenkron & Eşzamanlı (Concurrent) Runner Altyapısı
- **İşçi Havuzu Desteği:** `sloplab evaluate` ve `sloplab benchmark` komutlarına `-j / --concurrency` opsiyonu eklendi.
- **Deterministik Sıra Garantisi:** Eşzamanlı koşturulan testler, sıralı koşumla birebir aynı vaka sırasını ve sonuçlarını garanti eder.
- **`TokenBucketLimiter` & `ThrottledAsyncClient`:** Ani istek patlamalarını (burst) ve saniyedeki istek sayılarını asenkron yöneten thread-safe hız sınırlayıcılar entegre edildi.

### 1.3 Agentic / Tool-Use Triage Değerlendirici Sözleşmesi
- **`AgenticTriageEvaluator`:** Çok turlu (multi-turn) ReAct döngüsünü çalıştıran, araç çağrıları gerçekleştiren ve gözlemlere dayanarak karar veren yeni değerlendirici protokolü.
- **Mock Sandbox Araçları:**
  - `search_source_tree`: Kod tabanında savunmasız endpoint ve fonksiyonları tarar.
  - `execute_poc_sandbox`: İzole kum havuzunda PoC komutunu çalıştırarak HTTP yanıtını test eder.
- **Trace & Verimlilik Metrikleri:** `avg_tool_calls`, `tool_use_rate` ve adım adım `agent_trace` provenance kaydı.

### 1.4 Semantik Bozulma & Pertürbasyon Bütçesi Eğrileri
- **`compute_text_perturbation`:** Orijinal ve mutasyonlu metin arasındaki n-gram bazlı normalize mesafe (`1.0 - cosine_similarity`).
- **`perturbation_curve`:** Değerlendiricinin karar doğruluğunu pertürbasyon bütçesi dilimlerine bölerek (`[0.0-0.2], (0.2-0.4]...`) modelin dayanıklılık sınırlarını görselleştiren yeni metrik.

### 1.5 Resmi Güvenlik Suite'i: `v1-injection.yaml`
- Doğrudan LLM'lerin prompt injection direncini ölçmek için tasarlanmış bağımsız benchmark suite yapılandırması.

### 1.6 GitHub Actions CI/CD Pipeline
- `.github/workflows/ci.yml` ile Python 3.11, 3.12 ve 3.13 matrisinde `uv`, `pytest`, `ruff`, `mypy` ve `sloplab validate` otomasyonu.

---

## 2. Test ve Kalite Durumu

- **Toplam Birim / Entegrasyon Testi:** 201'den **233'e yükseltildi**, %100 başarı oranı (`233 passed`).
- **Linter & Formatter:** Ruff 0 hata, 657 dosya CommonMark ve PEP standartlarına uyumlu.
- **Tip Güvenliği:** Mypy strict mode, 88 kaynak dosyada 0 hata.
- **Korpus Doğrulaması:** 60 canonical fixture eksiksiz ve hatasız.
