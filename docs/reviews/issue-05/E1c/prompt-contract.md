# E1c — Prompt sözleşmesi

## Yetkili kaynak

Pilot için prompt kaynağı `repo_root / config.prompt_file`'dır. Göreli yol
`repo_root`'a, mutlak yol aynen kendine çözülür (pathlib `/` davranışı korunur).
Config prompt'u yetkilidir: sonradan dosyayı okuyup yalnız kimlik doğrulamak yeterli
değildir; gönderilen metin bu dosyadan gelir. Script (`llm_bench.py`) ve doğrudan
pilot API aynı davranışı sağlar (bağlama pilotun içindedir).

## Dondurma

Dosya yalnız bir kez okunur: ilk evaluator/transport çağrısından ve çıktı dizini
oluşturulmasından önce, UTF-8 (strict) çözülür. Aynı immutable metin tüm
vaka/tekrar/retry çağrılarında kullanılır. Ortadaki değişim/silim gönderilen metni
veya manifesto kimliğini değiştiremez; sonunda dosya tekrar hash'lenmez. Yükleme
sırasındaki eşzamanlı değişime karşı atomik snapshot iddiası yoktur (sonraki paket).

## Şablon kuralları

- Dosya tam bir `{report_text}` yer tutucusu içermeli. Sıfır/çoklu, okunamayan dosya,
  geçersiz UTF-8 → dispatch öncesi `PromptTemplateError` (bir `ValueError`); çıktı
  oluşmaz, dispatch sayısı sıfırdır.
- Renderer yalnız tanımlı yer tutucuyu tek geçişte işler (`str.replace`, `.format`
  yok): JSON süslü parantezleri, `{}`, LF/CRLF, Türkçe/Unicode ve rapor içindeki
  `{report_text}` aynen korunur, ikinci kez yorumlanmaz.

## İki render yolu

- **Legacy/default**: `LlmEvaluator(client=..., enabled=True)` kurucusu ve gönderilen
  default metin değişmedi; `PROMPT_TEMPLATE.format(...)` bayt-bayt korunur (sabitteki
  çift süslü parantezler bu yola aittir).
- **Dosya**: `with_prompt()` ile bağlanan doğrulanmış şablon, tek-geçişli renderer.
  `with_prompt` kopya döndürür (çağıran değişmez); aynı `CountingClient` nesnesi ve
  retry ayarları paylaşılır, sayaç sıfırlanmaz.

## Kimlik alanları

- `manifest.prompt_hash`: pilot başında okunan orijinal UTF-8 template **baytlarının**
  SHA-256'sı. Satır sonları normalize edilmez.
- `manifest.prompt_renderer_version`: render sürümü (`file-template-v1`); semantik
  değişirse yükseltilir.
- `evaluation_metadata.rendered_prompt_hash`: gönderilen **prompt metninin** UTF-8
  SHA-256'sı; her gözlemde (başarı/failed/retry) aynı. HTTP gövdesi/model/sampling
  içermez; tam request hash'i diye adlandırılmaz.
- Deterministik evaluator kayıtlarına yeni hash eklenmez. Ham LLM cevabı, credential
  ve prompt tamamı provenance alanlarına yazılmaz.

## Davranış değişimi notu

Eski pilotta hash'lenen dosya ile gönderilen sabit farklıydı. Bu paket pilotu gerçek
dosya prompt'una geçirdi: gönderilen metin değişti. Bu bir davranış değişimidir;
sadece metadata düzeltmesi değildir. Canlı pilot başlatılmadı.
