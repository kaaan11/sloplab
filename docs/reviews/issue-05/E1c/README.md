# E1c — Gönderilen prompt ile kaydedilen kimliği bağlama (teslim)

Durum: **E1c tamamlandı** (kabul ölçütleri karşılandı; E1'in tamamı kapanmadı).
Tarih: 2026-09-09. Kök: `/home/kaan/sloplab`. Yürütücü: Luna.
Önkoşul: E1b kabul edildi (`../E1b-acceptance.md`); E1a/E1b değişiklikleri korundu
(E1c uygulama kapsamı `adapter.py`, `pilot.py`, `llm_bench.py` ve yeni
`test_pilot_prompt.py`; önceki dirty değişiklikler aşağıdaki inceleme notunda ayrılır).

## Davranış

Pilot artık config prompt dosyasını çalışma başında bir kez okuyup dondurur
(`repo_root / config.prompt_file`; mutlak yol geçişli). Aynı immutable metin tüm
vaka/tekrar/retry çağrılarında kullanılır; ortadaki dosya değişimi/silimi gönderilen
metni ve manifesto kimliğini değiştirmez; sonunda yeniden hash'lenmez. Dosyada tam
bir `{report_text}` istenir; sıfır/çoklu yer tutucu, okunamayan dosya ve geçersiz
UTF-8 dispatch öncesi `PromptTemplateError` verir; çıktı oluşmaz.

`LlmEvaluator.with_prompt()` kopya bağlar: çağıranın evaluator'u değişmez, aynı
`CountingClient` nesnesi ve retry ayarları korunur, sayaç sıfırlanmaz. Varsayılan
kurucu ve gönderilen default metin bayt-bayt aynı (`PROMPT_TEMPLATE.format` yolu
korundu; dosya şablonları tek-geçişli renderer kullanır).

Manifestoda `prompt_hash` = okunan orijinal UTF-8 template baytlarının SHA-256'sı
(normalize yok) + açık `prompt_renderer_version` (`file-template-v1`). Her normalize
sonucun metadata'sında gönderilen prompt metninin SHA-256'sı `rendered_prompt_hash`
olarak taşınır (başarı/failed/retry aynı gözlemde aynı hash). Bu tam request hash'i
değildir. Deterministik kayıtlara yeni hash eklenmedi; ham cevap/credential/prompt
tamamı provenance'a yazılmadı.

Önemli: pilotun gerçek dosya prompt'una geçişi davranış değişimidir (önceden
gönderilmeyen dosya hash'leniyor, sabit template gidiyordu); sadece metadata
düzeltmesi değildir. Ayrıntı: `prompt-contract.md`.

## Değişen / yeni dosyalar

- `src/sloplab/evaluators/llm/adapter.py`: `PromptTemplateError`, `LoadedPromptTemplate`,
  `load/validate/render_file_template`, `PROMPT_RENDERER_VERSION`, `with_prompt`,
  `_render` (legacy `.format` + dosya renderer), iki sonuç yolunda `rendered_prompt_hash`.
- `src/sloplab/experiments/pilot.py`: `run_llm_pilot` başında tek yükleme + `with_prompt`
  bağlama; manifestoda `prompt_hash` (dondurulmuş baytlar) + `prompt_renderer_version`.
- `scripts/llm_bench.py`: `PromptTemplateError` → `configuration error`, exit 2 (dar sınır).
- `tests/regression/test_pilot_prompt.py` (yeni, 8 test fonksiyonu).
- E1c diff'i: `e1c.diff` (yalnız yukarıdaki 3 tracked dosya). Kapsam dışı (outcome,
  failed→review, severity, parser, bütçe/retry, sampling, kayıt kusurları, metrik)
  yapılmadı; rubric yeniden yazılmadı; canlı pilot yok.

## Test / doğrulama

- Yeni 8 + ilgili mevcut (adapter, pilot, script, snapshot, preflight, experiments,
  remediation): 87 passed. Tam paket: 233 passed. ruff/format/mypy: temiz. Mevcut
  test güncellemesi gerekmedi (metadata subset assertion'ları + prompt_hash truthy).
- Yeni koşu (`/tmp/sloplab-e1c-XWIRvj/run`) E0 `run-a` ile 480 küme eşit / 479 ham
  eşit (yalnız manifesto zamanları), suite-index ham bayt eşit; 297 vaka / 594 kayıt.
- Başlangıç dosya hash'i üretilmedi (ölçülmedi); geçmişe başlangıç yazılmadı. Bitiş
  hash'leri programatik + 64-hex doğrulamalı (`hashes-end.txt`, 18 satır). Koruma
  için `git diff --name-only` tek başına yeterli değildir; önceki dirty değişiklikleri
  de listeler. Ana inceleyicinin ek doğrulaması aşağıdadır.

## E1c durumu

**E1c tamamlandı.** Stimulus/hedef/seçim kimlikleri ve tam etkili tarif başka pakettir.

## Astra inceleme notu — 2026-09-09

55 hedefli test yeniden çalıştırıldı ve geçti; E0 karşılaştırması yeniden geçti.
18 bitiş hash'i güncel dosyalarla doğrulandı. `study.py`, `cli/main.py`,
`harness.py`, `test_study_preflight.py` ve `test_case_snapshot.py` dosyalarının
E1b bitiş hash'leriyle eşitliği ayrıca doğrulandı. Pilot E1c'de değiştiğinden
bu dosya hash eşitliğiyle değil E1b accessor delegesini koruyan diff ve testlerle
değerlendirildi. Kaydedilmemiş E1c başlangıç ölçümü geriye dönük üretilmedi.
Ayrıntı: `../E1c-acceptance.md`.
