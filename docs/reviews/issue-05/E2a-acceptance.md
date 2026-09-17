# E2a — Ana inceleyici düzeltmesi ve kabul kararı

Tarih: 2026-09-09. **E2a, ana inceleyici düzeltmesinden sonra kabul edildi. E2b sırada.**

## İnceleme sonucu

Worker teslimindeki typed failure, outcomes ledger, başarı/failure/not_run
muhasebesi, eksik coverage için stability kapısı ve evaluator label capability
sınırı kod ve testler üzerinden yeniden doğrulandı. Başarısız LLM sonucu artık
`CaseRecord` kararı değildir; legacy `metadata.failed=True` de ortak harness
sınırında typed failure'a dönüşür. Content evaluator'lar boş labels görür, oracle
açık opt-in ile kopya etiketi alır.

Worker'ın E1e referanslı offline koşusu 482 dosyalık kümeyi korudu: 480 ortak
veri/identity dosyası ham eşit, recipe semantik bağları ve 297 vaka/594 kayıt
uyumlu, manifestoda yalnız açıklanan zaman farkı var. Pilot failure yolu bilinçli
yeni protokoldür ve deterministik study run'ında yeni ledger üretilmez.

## İnceleyici düzeltmesi

Teslim doğrudan kabul edilmedi. Adapter timeout, transport ve bütçe exception
metinlerini ilk 200 karakteriyle `EvaluationFailure.detail` alanına, oradan da
`outcomes.jsonl` dosyasına yazıyordu. Sağlayıcı exception metni credential, URL,
ham cevap veya prompt parçası taşıyabildiği için bu, görevdeki kontrollü hata
açıklaması ve veri minimizasyonu sözleşmesine aykırıydı.

Ana inceleyici:

- parse, timeout, transport ve budget ayrımını koruyarak `detail` değerlerini
  kararlı sabit kodlara çevirdi;
- parser doğrulama değerlerinin ve exception metinlerinin ledger'a kopyalanmasını
  kaldırdı;
- credential/response canary taşıyan transport exception'ının typed failure
  metnine girmediğini doğrulayan regression testi ekledi;
- outcome şema belgesini sabit kod sözleşmesiyle güncelledi.

Retry sayısı, retry yetkisi, fiziksel dispatch muhasebesi ve parser kabul politikası
değiştirilmedi. Worker'ın eski diff/hash/log kayıtları korunmuştur; bunlar
inceleyici düzeltmesi öncesindeki teslimi tanımlar.

## Son doğrulama

- Adapter/outcome/pilot/prompt/snapshot kapsamındaki **61 hedefli test geçti**.
- Son kodla **tam offline paket 263 test geçti**.
- Değişen adapter/test dosyalarında ruff check ve format check temiz; adapter mypy
  temiz; `git diff --check` temiz.
- Gerçek API veya ağ isteği yapılmadı.

Tam paket yeniden çalıştırılırken ayrı bir `uv --collect-only` denemesi kullanıcı
cache dizinindeki geçici dosya kilidine/salt-okunur duruma takıldı. Aynı venv ile
collection bağımsız doğrulandı: 263 test. Bu, daha önce exit 0 ile tamamlanan tam
test koşusunun sonucu değildir ve kabulü değiştirmez.

## Kapsam ve sıradaki iş

E2a kabulü bütçe rezervasyon sahipliği, terminal/retry ayrımı, toplam deadline,
`Retry-After`, fiziksel attempt uzlaşması ve tam tekrar birliği için kabul değildir;
bunlar [E2b görevinde](../../issue-05-E2b-task.md) açık kalır. Bundle atomikliği ve
legacy reader E3'e, metrik formülleri E4'e aittir. E2 bütünü kapanmadı ve canlı
pilot başlatılabilir ilan edilmedi.
