# E1a — Deterministik study için erken ayar doğrulaması

Durum: Uygulamaya hazır; henüz yürütülmedi.  
Çalışma kökü: `/home/kaan/sloplab`. Yürütücü: Luna.  
Önkoşul: [E0 kabul kararı](reviews/issue-05/E0-acceptance.md).  
Üst plan: [Issue 05 mühendislik planı](issue-05-engineering-assessment-and-plan.md).

## 1. Amaç ve kapsam

Bu bir **kod uygulama görevidir**. Deterministik study şu anda evaluator config'ini hash'liyor fakat evaluator'a uygulamıyor. Bazı analysis/provenance bayrakları da ilan edilmesine rağmen etkisiz. Bilinmeyen evaluator adı ise materialization sonrasında fark edilebiliyor.

Bu pakette yalnız şu davranışı uygula: desteklenmeyen ayar veya bilinmeyen evaluator adı varsa **korpus üretimi, evaluator çalıştırması ve çıktı yazımı başlamadan** açıklayıcı hata ver. Mevcut desteklenen/default config'in çıktıları aynı kalmalı.

E1'in tamamını uygulama. StudySpec/CaseSnapshot mimarisi, prompt kimliği, yeni hash şeması, LLM, metrik düzeltmesi, kaynak düzenlemesi, bundle atomikliği ve bilimsel yöntem seçimi sonraki paketlerdir. Yeni framework, registry factory sistemi veya evaluator özelliği ekleme.

## 2. Okuma kapsamı

Geçerli AGENTS.md yönergelerini önce oku. Sonra bu dosya, E0 kabul kararı ve aşağıdaki dosyaların ilgili bölümleri yeterlidir:

- `src/sloplab/experiments/config.py`: DeterministicStudyConfig ve alt şemalar.
- `src/sloplab/experiments/study.py`: run_deterministic_study ve çağrı sırası.
- `src/sloplab/evaluators/base.py`: get_evaluator ve mevcut registry davranışı.
- `src/sloplab/cli/main.py`: study komutu ve hata sunumu için mevcut örnekler.
- `src/sloplab/experiments/runner.py`: load_study_config ve provenance üretimi.
- `tests/unit/test_experiments.py`, `tests/conftest.py`; CLI testi için mevcut yerleşimi `rg` ile bul.
- `experiments/configs/deterministic-study-v0.2.yaml` ve `benchmarks/suites/v1-core.yaml`.

Kaynak raporun tamamını veya bilimsel rapor dizinini okuma. Gereken doğrudan bağımlılığı sınırlı biçimde takip et; ek dosyanın nedenini teslimde belirt. Alt ajan başlatma.

## 3. Kesin davranış sözleşmesi

| Girdi | E1a davranışı |
| --- | --- |
| `evaluators[*].config == {}` | Desteklenir; mevcut davranış korunur. |
| Herhangi bir nonempty evaluator config | Reddedilir. Hata ilgili evaluator adını ve `evaluators[...].config` alanını belirtir. Key/value içeriğini gereksiz yere hata mesajına dökme. |
| Kayıtlı evaluator adı | Desteklenir. İsimleri iki baseline'a hard-code etme; mevcut kayıtlı evaluator'ları koru. |
| Bilinmeyen evaluator adı | Bütün evaluator adları çıktı üretiminden önce kontrol edilir; son sıradaki bilinmeyen ad da erken reddedilir. |
| `analysis.paired_comparison == False` | Bu bayrak henüz uygulanmadığından açıkça reddedilir. True korunur. |
| `analysis.error_taxonomy == False` | Aynı şekilde reddedilir. True korunur. |
| `provenance.record_commit_sha`, `record_suite_hash`, `record_evaluator_config_hash` alanlarından herhangi biri False | İlgili alan adıyla reddedilir. True korunur. |
| Geçerli `bootstrap_resamples`, `bootstrap_ci` | CLI'de uygulanıyor; mevcut şema aralıkları içindeki nondefault değerleri reddetme. |
| Study ve suite seed'lerinin farklı olması | Bu pakette yeni eşitlik şartı koyma. Generation seed suite'ten, analysis seed study'den gelmeye devam eder; açık kimliklendirme sonraki paketindir. |

False bayraklarını bu fazda uygulamayı seçme; kararlaştırılan çözüm desteklenmeyen talebi erken reddetmektir. Şemada kalıp doğrulanan alanlar, gelecekte destek eklenmesine engel değildir.

Doğrulama yalnız CLI'ye eklenmemeli: doğrudan `run_deterministic_study` çağrısı da aynı sınırı uygulamalı. Uygun şema validatörleri ve/veya küçük bir preflight fonksiyonu kullanabilirsin; rutin uygulama tercihleri için onay isteme. Bütün evaluator adlarının doğrulanmasını döngü içinde evaluator'lar çalıştırılırken yapma.

CLI hatası okunabilir olmalı; beklenen config hatasında traceback gösterilmemeli. Beklenmeyen program hatalarını geniş bir `except Exception` ile config hatası olarak gizleme. Registry lookup mesajlarını mevcut sözleşmeyle uyumlu tut.

## 4. Değişiklik sınırı

İzinli uygulama alanı: yukarıdaki experiments config/study modülleri; gerekliyse CLI study hata sınırı; doğrudan ilgili testler ve kısa kullanım/sözleşme belgesi. Yeni bir küçük regression dosyası eklenebilir.

- Evaluator karar/güven formülleri, metrikler, seed/tahsis, parser ve materializer davranışı değiştirilmez.
- Mevcut corpus, YAML config'leri, lock dosyası, eski study sonuçları ve E0 teslimi değiştirilmez.
- Provenance şemasına yeni alan veya sürüm eklenmez; bu sonraki paketin konusudur.
- Kullanıcının dirty/untracked değişikliklerini koru. Başlangıç git durumunu kaydet; commit/push veya branch değişikliği yapma.
- Canlı API/ağ/bağımlılık yükseltmesi yok. Offline ortam sorunu varsa bağımsız işi tamamla ve eksik doğrulamayı açıkça bildir.

## 5. Zorunlu kabul testleri

Testler uygulamayı taklit etmek yerine dış davranışı ve yan etki sırasını doğrulamalı:

1. Nonempty evaluator config, belirtilen iki analysis False bayrağı ve üç provenance False bayrağı ayrı parametreli örneklerle reddedilir; hata alanı bellidir.
2. Bilinmeyen ad evaluator listesinin sonunda olduğunda bile hiçbir evaluator çalışmaz ve materialization başlamaz. Spy/mock ile çağrı yokluğunu doğrula.
3. Doğrudan API ve CLI hata yollarını kontrol et. Yeni çıktı dizini hata durumunda oluşmamalı; önceden var olan geçici çıktı dizinindeki sentinel dosyasına veya dosya kümesine dokunulmamalı.
4. Boş config/default bayraklar kabul edilir. Desteklenen nondefault bootstrap ayarları ve farklı study/suite seed'leri yeni ret üretmez. Mevcut test fixture'larının küçük suite seed'lerini değiştirme.
5. CLI config hatası nonzero çıkış ve okunabilir mesaj verir; beklenen hatada traceback yoktur.
6. Başarılı deterministik study'nin E0 ile veri eşdeğerliği korunur.

Kaynak düzenlemesi için `apply_patch` kullan. Önce ilgili yeni testleri ve `tests/unit/test_experiments.py` dosyasını çalıştır; sonra kapsamla ilgili mevcut CLI testleri ve değişen dosyalarda lint/typecheck kontrollerini çalıştır. Repo yönergelerinin zorunlu kontrollerini uygula. Hedefli testler geçtikten sonra yeni neden olmadan aynı testleri tekrar tekrar çalıştırma.

## 6. E0'a karşı tek çalışma doğrulaması

Yeni geçici dizin oluştur (`mktemp -d /tmp/sloplab-e1a-XXXXXX`). Repo kökünden, gerçek yolu kullanarak:

```bash
uv run --offline --frozen sloplab study experiments/configs/deterministic-study-v0.2.yaml --out /tmp/GERCEK_E1A_DIZINI/run
```

Yeni çalışmayı `/tmp/sloplab-e0-zVHDyy/run-a` ile karşılaştır. E0 geçici çıktısı yoksa tarihsel `experiments/results/deterministic/study-v02/` kullanılabilir; eski yol/commit farklarının ayrıca açıklanması gerekir. Her iki referans da yoksa golden uydurma.

Tüm çıktı dosyalarının kümesi, records, derived dosyalar, analysis, rapor ve CSV ham bayt düzeyinde aynı olmalı. Aynı kökte E0 referansı kullanılıyorsa suite-index de ham eşit olmalı; manifesto yalnız açıklanan zaman alanlarında farklı olabilir. Mevcut E0 rev3 yardımcısını read-only kullanabilirsin; referans ile yeni çalışma arasındaki farkı geçirtebilmek için yardımcının allowlist'ini genişletme.

Karar, hedef, vaka sayısı veya metrik farkı bu pakette beklenmiyor. Varsa E1a kabulü durur; nedeni araştır, golden dosyaları güncelleme. Bu çalışma farklı bir bilimsel analiz sürümü değildir.

## 7. Teslim ve durma noktası

Teslim dizini: `docs/reviews/issue-05/E1a/`; doluysa üzerine yazmadan yeni numaralı kardeş seç.

- `README.md`: değişen davranış, değişen dosyalar, test/karşılaştırma sonuçları, sınırlamalar ve görev durumu.
- `config-support.md`: bu pakette desteklenen/reddedilen alanlar; seed rollerinin mevcut anlamı; E1'e kalan işler.
- `commands.jsonl`: her komutta gerçek komut, cwd, exit code ve log yolu. Çok satırlı komutları geçerli JSON string'iyle sakla; özet komutu gerçek yürütme kaydı diye yazma.
- `comparisons.md`: E0/yeni tam dosya kümesi ve hash farkları, vaka/kayıt sayısı, manifesto alan farkları.
- Test ve study stdout/stderr günlükleri ile yeni output hash envanteri; geçici run yolunu belirt.

İlgili uygulama diff'ini ve eklenen testleri workspace'te bırak; baştan var olan kullanıcı değişikliklerini kendi işin gibi sunma. Untracked dosyaların düz `git diff` çıktısında görünmediğini gözet; yeni dosyaları teslim listesinde açıkça say.

Kabul: desteklenmeyen config ve bilinmeyen ad bütün girişlerde yan etkiden önce reddedilir; desteklenen ayarlar gerilemez; E0 veri çıktıları değişmez. Teslim sonunda **E1a tamamlandı / kısmi** durumunu yaz, E1'in tamamını kapandı sayma. Sonraki pakete geçmeden Astra incelemesini bekle.
