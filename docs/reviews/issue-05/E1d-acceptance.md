# E1d — Ana inceleyici kabul kararı

Tarih: 2026-09-09. **E1d kabul edildi; E1e sırada.**

Yeni input_identity modülü, study bağlantısı, sekiz regression testi ve faz
karşılaştırma yardımcısı incelendi. Ana inceleyici 39 hedefli testi yeniden
çalıştırdı (input_identity, preflight, snapshot, experiments, CLI): hepsi geçti.
`compare_e1d.py` E0/yeni artefaktlarda RESULT: OK verdi. Eklenen tek dosya
input-identity.json; 479 eski veri/index dosyası ham eşit, manifestoda zaman farkı.

İç hash bağlarının kendi kendine tutarlılığına ek olarak, mevcut canonical/derived
kaynaklardan yüklenen 297 vaka için report_hash ve target_hash üretim helper'ları
çağrılmadan yeniden hesaplandı: tümü kayıtla eşit. Bitiş envanterindeki 10 dosya
güncel hash'lerle doğrulandı. Yeni study bu incelemede yeniden çalıştırılmadı.
Bağımsız hash kontrolü ilk denemede uv cache sandbox kilidine takıldı; izinli
offline tekrar başarıyla tamamlandı. Ağ çağrısı yapılmadı.

## Çözülen görev belirsizliği

Görev dosyası report_hash için hem raw_text UTF-8 hash'i hem bütün hash nesnelerinde
domain/type/version istiyordu. Worker sürümlü report nesnesini hash'lemiş; bu
kimlik tasarımı kabul edildi. Görev tanımı ve fonksiyon docstring'i aynı formüle
netleştirildi: SHA256(deterministik_JSON({domain,type,version,text})). Bu plain-text
veya disk dosyası hash'i değildir. Üretilmiş kimlikler, testler ve çalışma verileri
değişmedi; ana inceleyici davranış değiştiren bir patch uygulamadı.

Bloklayıcı uygulama bulgusu yok. Kimlik helper'ı snapshot yokluğunu reddediyor;
çalışma başında snapshot/target üzerinden yazılan nesne tekrar dosyadan türetilmiyor.
Tam reader doğrulama, source/ortam closure, atomik yayın veya mutable Python
nesnelerine karşı kapsamlı izolasyon sağlandığı iddia edilmiyor.

Sıradaki [E1e görevi](../../issue-05-E1e-task.md) E1'in etkili tarif kısmını tek
pakette tamamlar. Etiket yetkisi E2'ye, çapraz Python çıktısı E6'ya açıkça devredildi.
