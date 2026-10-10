# Kod Denetimi Raporu — 26 Eylül 2026

## Kapsam ve sonuç

- Proje: SlopLab
- İncelenen commit: `596d917c5d2fff7aa528efa8a03bd5e6660a2558`
- Son kontrol sırasında yerel `HEAD` ve `origin/main` aynı commit’teydi; GitHub’dan çekilecek fark görünmüyordu.
- Kapsam: `src/sloplab/` altındaki 64 Python dosyası, `scripts/llm_bench.py`, iki GitHub Actions workflow’u ve `pyproject.toml` olmak üzere 68 dosya.
- Sonuç: kaynakla çapraz kontrol edilmiş 23 bulgu: 14 orta, 9 düşük öncelikli.
- Denetim sırasında uygulama/konfigürasyon kodu değiştirilmedi ve test çalıştırılmadı. Bu rapor denetim tamamlandıktan sonra eklendi.
- Son 29 dilimlik bağımsız taramanın 4 çağrısı dosya içeriğine erişemedi, 2 çağrı boş yanıt verdi. Bu çıktılar bulgu sayılmadı; rapordaki bulgular kaynak koddan doğrulandı.

## Orta öncelikli bulgular

1. **Corpus manifest’i kök dışındaki dosyaları okutabilir.** Report yolu mutlak veya `..` bileşenleri içerdiğinde corpus kökü içinde kalma kontrolü yok. Güvenilmeyen bir corpus yüklenirse dışarıdaki dosya rapor metni olarak değerlendirme hattına girebilir. [loader.py:78](../src/sloplab/corpus/loader.py#L78)

2. **Suite index yolu materialized root dışına çıkabilir.** Derived manifest yolu kökle birleştiriliyor, ancak çözülmüş yolun kök içinde olduğu doğrulanmıyor. Güvenilmeyen veya değiştirilmiş bir index dışarıdaki fixture dosyalarının yüklenmesine yol açabilir. [harness.py:132](../src/sloplab/scoring/harness.py#L132)

3. **Analiz girdilerindeki records/outcomes yolları bundle dışına çıkabilir.** Analiz belgesinin records ve outcomes yolları bundle dizinine göre doğrulanmadan açılıyor. Hash kontrolü, dosya yolu için kök sınırı sağlamıyor. [analysis.py:239](../src/sloplab/reporting/analysis.py#L239), [analysis.py:253](../src/sloplab/reporting/analysis.py#L253)

4. **URL güvenlik filtresi bazı dış hostları izinli sanabilir.** URL regex’i authority bölümünü tam ayrıştırmıyor: örneğin `http://localhost@attacker.com` içindeki localhost kısmını host olarak algılayabilir. Ayrıca `endswith("localhost")` denetimi `fakelocalhost` değerini de yerel sayar. [policy.py:49](../src/sloplab/safety/policy.py#L49), [policy.py:57](../src/sloplab/safety/policy.py#L57)

5. **LLM bulgularındaki severity değerleri MEDIUM’a düşebilir.** Modelden beklenen küçük harfli severity değerleri enum üye adlarıyla karşılaştırılıyor. Geçerli `low` veya `high` değerleri eşleşmeyip varsayılan MEDIUM’a dönüşüyor. [adapter.py:375](../src/sloplab/evaluators/llm/adapter.py#L375)

6. **Koşullu sınır ifadesi denetimi cümle bağlamını kaçırabilir.** Koşul yalnızca eşleşmeden önceki 80 karakterde aranıyor; sonradan gelen koşullu ifade kaçabilir. Ayrıca herhangi bir eşleşmenin koşullu olması, ayrı bir koşulsuz sınır inkârını da maskeleyebilir. [baseline.py:239](../src/sloplab/evaluators/rules/baseline.py#L239)

7. **Eksik destek, sınır çelişkisi olarak raporlanıyor.** Etki iddiası veya sınır ifadesi bulunmadığında da e4 kenarı yok sayılıp GRAPH_BOUNDARY_CONTRADICTS_CLAIM bulgusu üretilebiliyor. [evidence_graph.py:161](../src/sloplab/evaluators/rules/evidence_graph.py#L161)

8. **Gözlemdeki çelişki, yanlışlıkla sınır inkârı olarak etiketleniyor.** Gözlenen sonuç iddiayı zayıflattığında BOUNDARY_NEGATED_BY_AUTHOR da ekleniyor; sınır ifadesi hiç inkâr edilmemiş olabilir. [evidence_graph.py:166](../src/sloplab/evaluators/rules/evidence_graph.py#L166)

9. **Benchmark, güvenlik nedeniyle atlanan vakalarla tamamlanmış görünebilir.** Materializasyon safety_violations döndürdüğünde benchmark komutu sonucu yazdırıp değerlendirmeye devam ediyor. Aynı durum materialize komutunda hata sayılıyor. [main.py:336](../src/sloplab/cli/main.py#L336)

10. **Çıktı dizini yeniden kullanıldığında eski hata kayıtları yeni analize karışabilir.** Yeni çalışmada hata yoksa study eski outcomes.jsonl dosyasını silmiyor veya üzerine yazmıyor. CLI bu dosyayı güncel başarısız değerlendirmeler gibi analiz ediyor. [study.py:214](../src/sloplab/experiments/study.py#L214), [main.py:469](../src/sloplab/cli/main.py#L469)

11. **Robustness puanı belgelenen canonical doğruluk bileşenini kullanmıyor.** Formülün yüzde 15’lik bileşeni canonical doğruluk diye açıklanmış; kod genel karar doğruluğunu kullanıyor. Canonical ve derived sonuçları farklıysa puan yanlış hesaplanıyor. [metrics.py:334](../src/sloplab/scoring/metrics.py#L334)

12. **Corpus doğrulaması yinelenen kimlikleri ve yetim parent’ları yakalamıyor.** Corpus düzeyinde canonical ID benzersizliği ve derived parent’ın varlığı kontrol edilmiyor; yinelenen veya parent’ı bulunmayan kayıtlar geçebilir. [validation.py:116](../src/sloplab/corpus/validation.py#L116)

13. **Markdown fence kapanışı açılış uzunluğuna göre doğrulanmıyor.** Dört backtick ile açılmış bir fence, üç backtick ile kapanmış sayılabilir. Bu durumda kod bloğundaki sonraki başlıklar rapor bölümü olarak ayrıştırılabilir. [parser.py:52](../src/sloplab/corpus/parser.py#L52)

14. **Başarısız LLM benchmark süreci başarılı çıkış kodu verebilir.** Komut başarısız değerlendirme sayısını yazdırdıktan sonra yine de 0 döndürüyor; CI veya otomasyon bunu başarı sayabilir. [llm_bench.py:186](../scripts/llm_bench.py#L186)

## Düşük öncelikli bulgular

1. **Başlığın sonundaki gerçek `#` karakteri silinebilir.** ATX kapanış işaretinde önce boşluk zorunlu tutulmadığından `# C#` başlığı C olarak ayrıştırılabilir. [parser.py:13](../src/sloplab/corpus/parser.py#L13)

2. **Expected Security Boundaries başlığı eşleşmeyebilir.** Pattern yalnızca tekil boundary biçimini arıyor; çoğul başlık required-evidence denetiminden kaçabilir. [conventions.py:15](../src/sloplab/corpus/conventions.py#L15)

3. **Küçük harfli CVE referansları safety kontrolünden kaçabilir.** CVE regex’i büyük/küçük harfe duyarlı. [policy.py:48](../src/sloplab/safety/policy.py#L48)

4. **Study provenance zamanı ve hata sayısı yanlış olabilir.** started_at değerlendirmeler bittikten sonra atanıyor; error_count ise başarısız sonuç olsa da varsayılan 0 kalıyor. [study.py:206](../src/sloplab/experiments/study.py#L206), [runner.py:92](../src/sloplab/experiments/runner.py#L92)

5. **Impact başlık eşleşmesi yanlış bölümü seçebilir.** Sınırlandırılmamış `impact` araması “Non-Impacted Systems” gibi bir başlıkla eşleşip mutasyonu o bölüme uygulayabilir. [impact.py:94](../src/sloplab/mutations/operators/impact.py#L94)

6. **Çift ünlem iki noktaya dönüşüyor.** Tek ünlem değiştirme işlemi önce çalıştığı için `!!` sonucu `..` oluyor. [presentation.py:143](../src/sloplab/mutations/operators/presentation.py#L143)

7. **Hedge mutasyonu sözcük sınırı kullanmıyor.** `likely` yerine koyma işlemi `unlikely` veya `likelihood` içindeki parçayı da değiştirebilir ve metni bozabilir. [presentation.py:217](../src/sloplab/mutations/operators/presentation.py#L217)

8. **Deadline nedeniyle çalışmayan vakalar bütçe atlaması sayılıyor.** `skipped_by_budget`, tüm `not_run` sayısına atanıyor; deadline kaynaklı atlamalar da bu alana giriyor. [pilot.py:707](../src/sloplab/experiments/pilot.py#L707)

9. **Compare sonuçları aynı adlı dizinlerde birbirini ezebilir.** Sonuç anahtarı evaluator adı ve dizin basename’inden oluşuyor; farklı üst dizinlerde aynı ada sahip iki çıktı tek kayda düşebilir. [main.py:587](../src/sloplab/cli/main.py#L587)
