# E1d — Vaka girdisi, hedef ve seçim kimlikleri (teslim)

Durum: **E1d tamamlandı** (kabul ölçütleri karşılandı; E1'in tamamı kapanmadı).
Tarih: 2026-09-09. Kök: `/home/kaan/sloplab`. Yürütücü: Luna.
Önkoşul: E1c kabul edildi (`../E1c-acceptance.md`); E1a/E1b/E1c değişiklikleri korundu
(korunan 7 dosyanın bitiş hash'i başlangıçla aynı; kapsam kanıtı aşağıda).

## Davranış

Deterministik study artık `build_cases` sonrasındaki aynı snapshot listesinden
`input-identity.json` üretir (ilk evaluator çalışmadan önce, bir kez). Dosya vaka
başına bir satır taşır (evaluator sayısı kadar çoğaltılmaz): mevcut `case_id`,
`case_kind`, `parent_id`, `operator`, `report_class`, `seed` + `report_hash`
(snapshot `raw_text` UTF-8 baytları), `target_hash` (sürümlü hedef nesnesi),
`input_hash` (ikisinin sürümlü bağı). Üstte `schema_version: 1`, sıralı seçim bağı
`selection_hash` ve sıralı satır bağı `inputs_hash`. Alan isimleri sözleşmedeki
gibidir. Ayrıntı: `schema-contract.md`.

Snapshot'sız vaka kimlik helper'ında kontrollü reddedilir (`InputIdentityError`);
legacy disk fallback hash üretimi için kullanılmaz; metin/manifest/hedef için
yeniden disk okuma yok. `records.jsonl`/`manifest.json` şeması değişmedi; pilota
ve evaluator'a kimlik alanı aktarılmadı; yeni dosya evaluator-visible input değildir.

## Uygulama tercihi

- Yeni modül `src/sloplab/experiments/input_identity.py` (görevde tercih edilen ad).
  `study.py`'ye küçük bağlantı: `build_cases` sonrası üret + yaz (E3 atomikliği yok).
- Mevcut `case_id`, seed/tahsis, kayıt ve analiz davranışı korundu (karşılaştırma kanıtlı).
- E1a preflight retleri çıktı üretmeme davranışını korur (preflight ilk satırda;
  kimlik yazımı `build_cases` sonrasındadır).

## Sınır

Tam etkili tarif, evaluator kaynak hash'i, ortam kilidi, analiz tanımı, reader
doğrulama/migration, atomic bundle ve pilot entegrasyonu dışarıda. Yeni dosya bütün
provenance sorunlarını çözmüş sayılmaz. Yükleme-anı atomikliği iddia edilmez.

## Test / doğrulama

- Yeni 8 kabul testi (`test_input_identity.py`): determinizm + key-sıra bağımsızlığı
  + bağımsız yeniden hesaplama; metin/hedef/sıra değişim matrisleri; eksik-boyut vs
  0.5 ayrımı; NaN/Infinity retleri; evaluator-listesi bağımsızlığı (iki gerçek study
  koşusu, bayt-eşit kimlik); iki geçici kökte aynı kimlik + path-sızıntı yokluğu;
  disk-değişim/loader-izolasyon/boş-snapshot; dosya/kayıt sıra uyumu (297 vaka).
- İlgili mevcut (study/preflight/snapshot/remediation/CLI): 54 passed. Tam paket:
  241 passed. ruff/format/mypy: temiz.
- Yeni koşu (`/tmp/sloplab-e1d-jJOgHz/run`) vs E0 `run-a`: E0 rev3 helper'ı (değişmeden)
  tek ek dosyayı reddetti (exit 1, beklendiği gibi); faza özel `helpers/compare_e1d.py`
  exit 0: kümede yalnız `input-identity.json` ek, 479 ortak dosya ham eşit, manifesto
  yalnız zamanlarda farklı, kimlik iç bağları + 297 vaka/594 kayıt uyumu doğrulandı.
  Bozulmuş kimlik negatif kontrolü exit 1 ile reddedilir.

## Teslim ve E1d durumu

`README.md`, `schema-contract.md`, `comparisons.md`, gerçek `commands.jsonl`,
günlükler, `hashes-start/end.txt`, bağımsız `e1d.diff` (yalnız `study.py`; yeni
modül + test untracked listede), `run-outputs.sha256` (481 dosya). Büyük run
`/tmp/sloplab-e1d-jJOgHz/` altında; kalıcı arşiv garantisi yok.

**E1d tamamlandı.** Sonraki paket etkili recipe/seed/config kimliğidir; E1'in tamamı
kapanmadı, bütün okuyucular doğrulanmış ilan edilmedi.
