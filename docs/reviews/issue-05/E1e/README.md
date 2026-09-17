# E1e — Etkili deney tarifini bağla, E1'i kapat (teslim)

Durum: **İnceleyici düzeltmesinden sonra kabul edildi**; aşağıdaki worker kayıtları
ilk teslimi tanımlar. Son durum: `../E1e-acceptance.md`.
Tarih: 2026-09-09. Kök: `/home/kaan/sloplab`. Yürütücü: Luna.
Önkoşul: E1d kabul edildi (`../E1d-acceptance.md`); önceki değişiklikler korundu
(`git diff --name-only` bu turda yeni tracked dosya eklemedi; dokunulmayan 4 dosya
start==end doğrulandı; E1a–E1d suites tam pakette yeşil).

## Davranış

Çalışma başında tek çözümleme sınırında tarif dondurulur: yüklenen suite nesnesi
(aynı nesne materializer'a verilir, dosya tekrar okunmaz), bir kez çözümlenmiş
evaluator nesneleri (çalışma döngüsü registry'ye tekrar sormaz; thread/process
güvenliği iddia edilmez), repeat_index + provenance seçenekleri. Kopyadaki
bootstrap ayarları CLI analizini besler; orijinal config'e dönülmez. API analiz
üretmez ve ürettiği iddia edilmez (tarifte tamamlanma iddiası alanı yoktur).

`execution-recipe.json` (`schema_version: 1`): generation/evaluation/analysis
bölümleri + ayrı hash'leri (domain/type/version zarflı, E1d encoding),
`settings_hash`, aynı in-memory identity'den `inputs_hash`/`selection_hash`,
`execution_hash`; `locations` (çözümlenmiş mutlak yollar, hash dışı);
`metadata` (HEAD, dirty göstergesi — tam kod kimliği değildir — Python, paket,
lock SHA; settings'e karışmaz; shell dökümü/credential yok). Mevcut
records/analysis/manifest/input-identity şemaları değişmedi. Ayrıntı:
`recipe-contract.md` (koddan önce yazıldı, uygulama/test aynen izledi).

## Değişen / yeni dosyalar

- `src/sloplab/experiments/resolved_recipe.py` (yeni): frozen tarif nesneleri
  (scalar/tuple alanlar; `instances` karşılaştırma dışı), çözümleme, hash'ler,
  dosya yazımı.
- `src/sloplab/experiments/input_identity.py` (E1d'den untracked'tı; bu tur
  genişletildi): herkese açık `canonical_json_bytes` + `tagged_digest(domain=...)`;
  E1d varsayılan yolu davranış-değişmeden delege eder (E1d testleri yeşil).
- `src/sloplab/experiments/study.py`: sınırda `resolve_recipe`, aynı suite nesnesi,
  çözümlenmiş nesnelerle döngü, tarif + kimlik yazımı, `StudyRunResult.recipe`
  (ek alan; imza korundu).
- `src/sloplab/cli/main.py`: bootstrap parametreleri `result.recipe.analysis`'ten.
- `tests/regression/test_resolved_recipe.py` (yeni, 8 test).
- E1e diff'i: `e1e.diff` (yalnız tracked `study.py` + `cli/main.py`; yeni modül/test
  untracked listede). Evaluator formülleri, materializer/scoring, LLM/pilot
  protokolü değişmedi; framework/PRNG/factory yok.

## Test / doğrulama

- Yeni 8 + ilgili mevcut (identity, experiments, preflight, snapshot, remediation,
  CLI, pilot, script, adapter): 98 passed. Tam paket: 249 passed. ruff/format/mypy
  temiz. Ara hata (`_tagged_object` domain yoksayması, test yaml ad çakışması)
  testlerle yakalanıp düzeltildi.
- Yeni koşu (`/tmp/sloplab-e1e-w2dMaH/run`) vs E1d ref: E0 rev3 helper değişmeden
  reddetti (exit 1, iki ek dosya — beklendiği gibi); faza özel `helpers/compare_e1e.py`
  exit 0 (yalnız `execution-recipe.json` ek, 480 ortak ham eşit, manifesto yalnız
  zamanlar, iç bağlar + 297×594 uyumu). Bozulmuş tarif negatifte reddedilir.

## E1a–E1e kapanış matrisi

| Paket | Kapanan | Durum |
| --- | --- | --- |
| E0/G0 | Referans + bulgu doğrulama | kabul |
| E1a | Desteklenmeyen ayar/bilinmeyen ad erken reti | kabul |
| E1b | Çalışma-boyu snapshot girdisi | kabul |
| E1c | Prompt kimliği + rendered hash | kabul |
| E1d | Girdi/hedef/seçim kimlikleri | kabul |
| E1e | Çözülmüş etkili tarif + recipe kimlikleri | **bu teslim** |

Kayıtlı girdi kimliği ile uygulanan ayarlar artık açık: tarif bölümleri, ayrı
generation/analysis seed'leri, çözümlenmiş evaluator nesneleri, kopyadan beslenen
CLI analizi ve `execution_hash` bağı dosyada.

## E2/E3/E4/E6'ya devredilen açık maddeler (E1'de kapanmadı sayılmadı)

- **E2**: evaluator etiket erişim yetkisi; terminal bütçe/transport hatası ayrımı.
- **E3**: reader/bundle doğrulama, migration, atomic yayın protokolü.
- **E4**: metrik semantiği (ağırlık, ECE, susceptibility, CI yorumları).
- **E6**: çapraz ortam/Python byte garantisi, desteklenen-ortam taahhüdü.
- Ayrıca: evaluator kaynak-kodu hash'i, tam source closure, provider determinism,
  genel subclass/factory uyumluluğu — hiçbiri bu pakette iddia edilmedi.

## E1 tamamlandı önerisi

E1a–E1e kabul ölçütleri karşılandı; E1'in **kapatılması ana inceleyiciye
önerilir**. E2'ye kendiliğinden geçilmeyecek.

## Astra inceleme düzeltmesi

İlk teslimde mutable config bağı tam kesilmemişti. Güçlendirilmiş test evaluator
listesi sonradan boşaltılınca çalışmanın çöktüğünü gösterdi. Ana inceleyici özel
config/suite kopyaları, çözülmüş evaluator döngüsü/provenance ve sabit rapor adı
bağlantısını ekledi. Son tam test paketi 249 passed; yeni review study eşdeğerliği
geçti. İlk teslim hash/log/diff'leri geçmiş kayıt olarak korunur, son kodun
hash envanteri diye kullanılmaz. Ayrıntı `../E1e-acceptance.md`.
