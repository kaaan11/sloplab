# E6 — Çapraz ortam garantisi ve koşullu performans

Durum: Koşullu; bütünleşik kapanış profilinin gerekçelendirmesiyle çalıştırılır.
Ortak kurallar: [worker teslim protokolü](issue-05-worker-delivery-protocol.md).

İki desteklenen interpreter/ortam ve farklı köklerde aynı offline girdileri
çalıştır. Değişken metadata politikasını koşudan önce sabitle; test edilmemiş
ortam için garanti verme. Materialization, parse/load, evaluator, analiz ve yazım
sürelerini tekrarlı ölç; dağılım ve ortamı kaydet.

Worker havuzu yalnız ölçülmüş anlamlı darboğaz varsa ayrı öneri/uygulama olarak
ele alınabilir. Paralellik evaluator state'ini, config/vaka sırasını, bootstrap
akışını ve veri baytlarını değiştirmemelidir. `%20` bir kabul taahhüdü değildir;
kazanç, varyasyon ve bakım maliyeti birlikte raporlanır. Darboğaz yoksa optimizasyon
yapmadan “gerekçelendirilmedi” hükmü başarılı teslimdir.
