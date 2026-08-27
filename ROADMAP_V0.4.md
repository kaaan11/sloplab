# SlopLab V2 - Stratejik Geliştirme Yol Haritası (v0.4.0+)

Bu yol haritası, `sloplab_v2` bünyesinde tamamlanan Faz 1 - Faz 8 mimari iyileştirmelerinin ardından, sistemi tam teşekküllü bir **AI & LLM Güvenlik Benchmark ve Triage Kıyaslama Platformu** haline getirecek operasyonel ve mühendislik adımlarını içerir.

---

## Genel Bakış ve Faz Yapısı

```mermaid
flowchart LR
    F9[Faz 9: v1-injection.yaml Suite] --> F10[Faz 10: CI/CD Pipeline]
    F10 --> F11[Faz 11: Canlı LLM Pilot Doğrulama]
    F11 --> F12[Faz 12: v0.4.0 Release & Tag]
```

---

## 1. Faz 9: Özel Güvenlik Suite'i (`v1-injection.yaml`) & Benchmark Konfigürasyonu
* **Öncelik:** P1 (Yüksek)
* **Kategori:** AI Security / Benchmark Standardizasyonu
* **Amaç:** Faz 5'te eklenen indirect prompt injection (`evaluator_override_injection`, `markdown_polyglot_injection`) operatörlerini sistematik bir benchmark paketine dönüştürmek.

### Yapılacak İşlemler:
- [ ] `benchmarks/suites/v1-injection.yaml` konfigürasyonunun oluşturulması:
  - Valid, invalid ve review sınıflarında injection operatörlerinin dağılım kuralları.
  - Hedeflenen mutasyon varyant oranları (`variants_per_fixture`).
- [ ] Materyalize edilmiş referans vaka dizininin (`benchmarks/results/v1-injection-example/`) üretilmesi.
- [ ] CLI `benchmark` ve `evaluate` komutlarında injection metriklerinin (`attack_success_rate`, `injection_resistance_rate`) raporlama özetine (`report.md`, JSON) entegrasyonu.
- [ ] Kapsamlı regresyon testleri (`tests/unit/test_suite_injection.py`).

### Başarı Kriteri:
```bash
sloplab benchmark benchmarks/suites/v1-injection.yaml --evaluator rules-baseline --out /tmp/injection-run
```
komutunun sorunsuz çalışması ve ASR / IRR metriklerini raporlaması.

---

## 2. Faz 10: GitHub Actions CI/CD Pipeline Entegrasyonu
* **Öncelik:** P1 (Yüksek)
* **Kategori:** DevOps / Kod Kalitesi Güvencesi
* **Amaç:** Repoya gönderilen her commit ve PR için otomatik test, lint ve tip denetimini garanti altına almak.

### Yapılacak İşlemler:
- [ ] `.github/workflows/ci.yml` dosyasının oluşturulması:
  - Matris testi: Python 3.11, 3.12, 3.13.
  - `astral-sh/setup-uv` ile ultra hızlı ortam kurulumu.
  - Adımlar:
    1. `uv sync --all-groups`
    2. `uv run ruff check .`
    3. `uv run ruff format --check .`
    4. `uv run mypy src tests`
    5. `uv run pytest -v`
    6. `uv run sloplab validate corpus/`
- [ ] Otomatik release iş akışı (`.github/workflows/release.yml`) hazırlığı.

### Başarı Kriteri:
GitHub remote üzerinde yeşil pipeline doğrulaması (sıfır hata, sıfır warning).

---

## 3. Faz 11: Canlı Model ile Ampirik LLM Pilot Çalıştırması
* **Öncelik:** P2 (Orta)
* **Kategori:** Ampirik AI Güvenlik Araştırması
* **Amaç:** Sentetik ve mock testlerin ötesine geçerek gerçek bir açık kaynak veya ticari modelin prompt injection'a karşı dayanıklılığını ölçmek.

### Yapılacak İşlemler:
- [ ] Yerel model (Ollama / vLLM: örn. `llama3.1:8b`, `qwen2.5-coder:7b`) veya API (OpenAI / Anthropic / Gemini) entegrasyon yapılandırması.
- [ ] `experiments/configs/llm-pilot-live.yaml` dosyasının hazırlanması (istek bütçesi, token limiter, timeout).
- [ ] `sloplab pilot` koşturularak modelin:
  - Prompt Injection karşısındaki Saldırı Başarı Oranı (`ASR`).
  - Kalibrasyon Hatası (`ECE`).
  - Yanıltıcı Güven Oranı (`False Reassurance Rate`).
  - Karar kararlılığı (`Repeat Stability`).
- [ ] Elde edilen ampirik sonuçların `docs/empirical-pilot-results.md` olarak dokümante edilmesi.

### Başarı Kriteri:
Gerçek bir LLM üzerinden en az 10 kanonik + 20 injection vakasının canlı değerlendirilmesi ve raporlanması.

---

## 4. Faz 12: v0.4.0 Sürüm Yükseltme, Dokümantasyon & GitHub Release
* **Öncelik:** P2 (Orta)
* **Kategori:** Sürüm Yönetimi
* **Amaç:** Faz 5-11 arasındaki tüm yenilikleri resmi bir minör sürüm (`v0.4.0`) altında paketlemek.

### Yapılacak İşlemler:
- [ ] Sürüm artırımı:
  - `pyproject.toml` -> `0.4.0`
  - `src/sloplab/__init__.py` -> `0.4.0`
  - `docs/dataset-card.md` -> `0.4.0`
  - `uv.lock` senkronizasyonu.
- [ ] `docs/release-notes-v0.4.0.md` hazırlanması:
  - Indirect Prompt Injection operatörleri (`EvaluatorOverrideInjection`, `MarkdownPolyglotInjection`).
  - Asenkron & Eşzamanlı (Concurrent) değerlendirme altyapısı (`-j / --concurrency`).
  - Agentic / Tool-Use Triage Değerlendirici Sözleşmesi (`AgenticTriageEvaluator`).
  - Semantik Pertürbasyon Mesafesi ve Dayanıklılık Eğrisi (`perturbation_curve`).
- [ ] Git tag (`v0.4.0`) oluşturulması ve GitHub Release yayımlanması.

---

## Uygulama Sıralaması

| Sıra | Faz | Kapsam | Tahmini Efor |
|---|---|---|---|
| **1** | **Faz 9** | `v1-injection.yaml` suite ve benchmark entegrasyonu | Kısa |
| **2** | **Faz 10** | GitHub Actions CI/CD boru hattı (`ci.yml`) | Kısa |
| **3** | **Faz 11** | Canlı LLM pilot testi ve ampirik sonuç dokümantasyonu | Orta |
| **4** | **Faz 12** | `v0.4.0` sürüm artırımı, release notes ve tag | Kısa |
