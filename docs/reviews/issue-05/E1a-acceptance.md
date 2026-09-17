# E1a — Ana inceleyici kabul kararı

Tarih: 2026-09-09. İnceleyici: Astra. Durum: **E1a kabul edildi. E1 bütünü açık.**

## İnceleme ve kanıt

`experiments/study.py` ve CLI study diff'i, yeni `test_study_preflight.py`, destek matrisi ve teslim günlükleri incelendi. Preflight, doğrudan API'nin başında, korpus discovery/materialization öncesinde çağrılıyor. Nonempty evaluator config, desteklenmeyen False bayrakları ve bilinmeyen evaluator isimleri burada reddediliyor. CLI yalnız beklenen config hata türlerini kullanıcı hatasına çeviriyor; çalışma etrafında genel exception yakalama eklenmemiş.

Ana inceleyici tarafından yeniden çalıştırılan kontroller:

```bash
uv run --offline --frozen pytest -p no:cacheprovider tests/regression/test_study_preflight.py tests/unit/test_experiments.py tests/unit/test_cli.py
python3 -B docs/reviews/issue-05/E0/helpers/compare_e0.py /tmp/sloplab-e0-zVHDyy/run-a /tmp/sloplab-e1a-ppqPYl/run /tmp/sloplab-e0-zVHDyy/run-a
git diff --check
```

Sonuç: **20 test geçti**, karşılaştırma `RESULT: OK`, diff kontrolü temiz. 480 dosyalık çıktı kümesi aynı; 478 dosyanın hash'i ve suite-index baytları eşit, manifesto yalnız başlangıç/bitiş zamanlarında farklı. Bu tur yeni study çalıştırılmadı; teslimdeki çalışma artefaktları tekrar karşılaştırıldı.

Worker'ın tam test günlüğü ayrıca okundu: 214 passed. Bu sayı ana inceleyicinin yeniden çalıştırdığı 20 testten ayrıdır. Worker'ın lint/typecheck beyanları bu tur yeniden çalıştırılmadı.

## Karar ve sınırlar

E1a kapsamındaki uygulamada bloklayıcı bulgu yok; düzeltme gerekmedi. Registry lookup'un preflight ve çalışma döngüsünde tekrar yapılması mevcut kapsamda kabul edilebilir; çözülmüş tarif veya registry snapshot garantisi sağlandığı anlamına gelmez.

Malformed YAML dahil her türlü config/file hatasının genel CLI politikası, bağımsız bir kapsamdır; bu paketin kabulü belirtilen unsupported alanlar ve bilinmeyen evaluator adları içindir. Test ve run günlüklerinin bir bölümü `/tmp` içindedir; kalıcı arşiv sayılmaz.

Teslim README'sindeki “480/480 dosya eşit” ifadesi, aynı cümlede belirtilen manifesto istisnasıyla okunmalıdır: ham eşitlik 479 dosya, dosya kümesi eşitliği 480 dosyadır. Destek matrisindeki True analysis bayrakları da seçim dalı uygulanması anlamına gelmez; ilgili çıktılar mevcut CLI'de daima hesaplanır ve False artık reddedilir.

Sonraki dar teslim: [E1b — Çalıştırma boyunca sabit rapor girdisi](../../issue-05-E1b-task.md). Önceki E1a değişiklikleri korunacak; E1b diff'i bunlardan ayrı raporlanacak.
