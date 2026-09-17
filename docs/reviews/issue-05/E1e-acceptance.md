# E1e — İnceleyici düzeltmesi ve E1 kapanışı

Tarih: 2026-09-09. **E1e, Astra düzeltmesinden sonra kabul edildi. E1 kapatıldı.**

## Bulgu ve düzeltme

Worker teslimi doğrudan kabul edilmedi. Recipe kopyalanmasına rağmen study döngüsü
`zip(config.evaluators, recipe.instances)` kullanıyor; manifest alanları da orijinal
mutable config'ten üretiliyordu. Çözümleme sonrası caller'ın evaluator listesini
boşaltması çalışmayı `ValueError: zip() argument 2 is longer than argument 1` ile
durdurdu. Seed/repeat değişiklikleri de yanlış manifesto yazma riski taşıyordu.

Test önce bu karşıörnekle güçlendirildi ve başarısız olduğu görüldü. Ardından:

- Study girişinde config, yükleme sınırında suite deep-copy ile özel kopyaya alındı.
- Evaluator döngüsü `recipe.evaluators` ve `recipe.instances` üzerinden bağlandı.
- Evaluator provenance'ı çözülmüş ad/version/config kopyalarını kullanıyor.
- CLI rapor adı `StudyRunResult.experiment_name` üzerinden özel config kopyasından
  geliyor; orijinal cfg'ye analiz sonrasında geri dönmüyor.
- Test artık seçilmeyen yeni bir registry anahtarı eklemek yerine gerçekten
  seçilen anahtarı çözümleme sonrasında değiştiriyor. Loader'ın elindeki suite
  nesnesini üretimden önce değiştiriyor; kayıt ve manifesto eşitliğini doğruluyor.

Değişen dosyalar: study.py, cli/main.py, test_resolved_recipe.py. Worker'ın eski
hash/diff/log kayıtları korunmuştur; bunlar inceleyici düzeltmesi öncesini tanımlar.

## Son doğrulama

- Güçlendirilmiş test düzeltme öncesinde 1 failed; düzeltme sonrasında recipe
  testleri 8 passed. Ara ilgili test çalışmasında 47 passed.
- Son kodla **tam test paketi 249 passed** (ana inceleyici tarafından çalıştırıldı).
- Değişen üç dosyada ruff check, format check ve mypy temiz; git diff --check temiz.
- Yeni offline study: `/tmp/sloplab-e1e-review-hoxabV/run`, 297 vaka/2 evaluator.
- E1d `/tmp/sloplab-e1d-jJOgHz/run` referansına karşı `compare_e1e.py` RESULT: OK.
  Yalnız execution-recipe.json ek; 480 ortak veri/identity dosyası ham eşit,
  manifestoda yalnız zaman farkı. Hash iç bağları ve 297 vaka/594 kayıt uyumu geçti.

Test/kalite kontrollerinin bir denemesi uv cache sandbox kilidine takıldı; izinli
offline tekrar başarıyla tamamlandı. Gerçek API/ağ isteği yapılmadı.

## Kapanışın kapsamı

E1a–E1e ile desteklenmeyen ayar reti, vaka snapshot'ı, prompt kimliği,
metin/hedef/seçim bağı ve uygulanan tarif bağlantısı kapandı. E1'in kapanışı
reader doğrulama/atomiklik (E3), outcome/bütçe ve etiket yetkisi (E2), metrikler
(E4), kaynak düzeltmesi (E5) veya çapraz ortam garantisi (E6) için kabul değildir.
Kod/ortam metadata'sı tam source closure veya kurulu ortam attestation'ı değildir.
Config deep-copy, keyfi evaluator nesnesinin bütün internal state'ini dondurmaz.

Yeni kod çalışma ağacında dirty durumdadır; commit yapılmadı. Son kabul edilen
referans yukarıdaki review run'dır; worker'ın eski run'ı silinmedi.

Sıradaki: [E2a görev dosyası](../../issue-05-E2a-task.md).
