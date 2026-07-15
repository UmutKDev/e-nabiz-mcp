# Bulgu: Veri modelleri / yanıt şekilleri (canlı)

> Endpoint yanıtları keşfedildikçe alan sözlüğü ve örnek şekiller buraya işlenir.
> **Gizlilik:** gerçek hasta verisi örnekleri buraya yazılmaz; yalnızca alan
> adları, tipleri ve anonim/uydurma örnekler.

## Şablon (her veri alanı için)

```
### <Alan adı> — endpoint: <URL>
- Format: JSON | HTML tablo | ...
- Sayfalama: var/yok (parametreler: ...)
- Alanlar:
  | alan | tip | açıklama | örnek (anonim) |
  |---|---|---|---|
```

---

## Tahliller / Tetkikler — endpoint: `POST /Tahlil/Index` ✅

- **Format:** HTML accordion partial (JSON değil). BeautifulSoup ile parse edilir.
- **İstek:** `{ baslangicTarihi: "<yıl>", bitisTarihi: "<yıl>", activeTab: "0" }`
  (yıl bazlı filtre; yıllar `#baslangicyilSelect` seçeneklerinden: 2014…2026).
- **Yapı:**
  - `.accordion-item` = bir tarih/ziyaret grubu
    - `.zCardDateGun` / `.zCardDateAy` / `.zCardDateYil` → tarih parçaları
    - `.hastaneAdi` → kurum adı
    - `.rowContainer` = tekil test (6 `.columnContainer` kolonu):

| Kolon | İçerik | Parser alanı |
|---|---|---|
| [0] `.islemAdiContainer` | test/tetkik adı | `test` |
| [1] | sonuç değeri | `value` |
| [2] | birim | `unit` |
| [3] | referans aralığı | `reference` |
| [4] `.karsilastirmaContainer` | trend butonu → `GrafikGoster(...)` / `TahlillerRapor` | `trend_code` |
| [5] `.durumNormal` \| `.durumRefdisi` | SUNUCUNUN referans durumu | `status` |

> ⚠️ **Her columnContainer bir etiket `<span>` içerir** (`<span>Sonuç :</span>8,54`) → değer
> yalnız span DIŞINDAKİ metindir (`_col_value`; span metnini almak `value`'yu bozardı — 2026-07-14 düzeltildi).
>
> ⚠️ **`status` sunucunundur; `out_of_range` bizimdir.** E-Nabız iki-uçlu referansları
> ("9,3-12,1") değerlendirir ama **tek-üst-sınırlı** ("-2,7") ve boş ("-") referansları
> değerlendirmeyip `durumNormal`'e düşürür (ör. HOMA-IR 8,54 / ref "-2,7" → sunucu "normal").
> Bu yüzden `LabResult.out_of_range` = value↔reference BAĞIMSIZ kontrolü (`-Y`/`Y-`/`<Y`/`>X`/
> `X-Y`, virgüllü ondalık; çözülemezse `None`). Canlı: sunucunun "normal" dediği sonuçların bir kısmı
> `out_of_range=True`.

- **Pydantic modeli:** `LabReport{date, hospital, card_tarih, kurum_kodu,
  results: [LabResult{test, value, unit, reference, status, out_of_range, trend_code}]}`.
- **Doğrulama (canlı):** çok sayıda rapor/test; value/unit/reference etiketsiz
  temiz; sunucunun `status` alanı normal/ref_disi ayrımı yapıyor ve `out_of_range`
  sunucunun kaçırdığı vakaları yakaladı ✅ (sayılar yazılmaz — referans-dışı sonuç
  ADEDİ klinik bulgudur).

---

## Reçeteler — endpoint: `POST /Recete/Index {baslangicYil, bitisYil}` ✅

- **Format:** HTML tablo `#tbl-recetelerim` (accordion değil). Kolonlar:
  **Tarih · Reçete No · Reçete Türü · Hekim · Karekod · (aksiyon)**.
- Detay butonu: `ReceteDetayGoster(sysTakipNo, receteNo, hekim, tur)` →
  `POST /Recete/GetReceteDetay?data={"SYSTakipNo":..,"ReceteNo":..}`.
- **Model:** `Prescription{date, prescription_no, type, doctor, sys_takip_no}`.
- **Doğrulama (canlı):** onlarca reçete; tüm alanlar istisnasız dolu.

### Reçete detayı — `POST /Recete/GetReceteDetay` ✅
İki tablo döner:
- `tbl-RecetedeYazan…` (yazılan): Barkod · İlaç Adı · Açıklama · Doz · Periyot ·
  Kullanım Şekli · Kullanım Sayısı · Kutu Adedi
- `tbl-RecetedeSatilan…` (satılan): Barkod · İlaç Adı · Kutu Adedi
- **Model:** `PrescriptionDrug{category(prescribed|dispensed), barcode, name, description,
  dose, period, usage, usage_count, box_count}` (id'de Türkçe `İ` → parser "Yazan"/"Satilan"
  ASCII substring'i ile eşler). **Doğrulama:** ilk reçete → 1 yazılan + 1 satılan.

---

## Sağlık raporları — endpoint: `POST /Rapor/Index {startYear, endYear}` ✅

- **Format:** HTML tablo `#tblRaporlarim`, self-contained (detay çağrısı yok). Kolonlar:
  **Tarih · Rapor No · Rapor Takip Numarası · Rapor Türü · Başlangıç Tarihi ·
  Bitiş Tarihi · Tanı · (aksiyon ×2)**.
- **Model:** `Report{date, report_no, tracking_no, type, start_date, end_date, diagnosis}`.
- **Doğrulama (canlı):** onlarca rapor; 7 alanın hepsi istisnasız dolu.
- **Uyarı:** yıl paramları `startYear`/`endYear` (reçete `baslangicYil`, tahlil
  `baslangicTarihi` — her endpoint farklı; bkz. endpoints.md).

---

## İlaçlar — endpoint: `POST /Ilac/Index {baslangicYil, bitisYil}` ✅

- **Format:** HTML tablo `#tblIlaclarim`, 13 kolon, self-contained (reçete bazlı düz
  ilaç listesi). Kolonlar: **Reçete Tarihi · Barkod · Reçete No · İlaç Adı · Doz ·
  Periyot · Kullanım Şekli · Kullanım Sayısı · Kutu Adedi · Hastane Adı · Klinik Adı ·
  (Kutu Resmi, Prospektüs = aksiyon)**.
- **Model:** `Medication{prescription_date, barcode, prescription_no, name, dose,
  period, usage, usage_count, box_count, hospital, clinic}`.
- **Doğrulama (canlı):** onlarca ilaç; tüm alanlar dolu.

> **Reçete detayı vs. İlaçlar:** `GetReceteDetay` bir reçetedeki ilaçları verir;
> `/Ilac/Index` tüm ilaçları hastane/klinik bağlamıyla düz listeler. İkisi tamamlayıcı.

---

## Radyoloji — sayfa kartları + `POST /RadyolojikGoruntu/GetRaporByOrder {orderId}` ✅

- **Liste formatı:** `/Home/RadyolojikGoruntulerim` sayfasındaki `.radyolojiCardListe`
  kartları (tablo/accordion değil). Kart alanları: `.RhastaneAdi` (kurum), `.Rtarih`
  (tarih, iki kez → ilki alınır), `.Raciklama` (açıklama). Rapor butonu:
  `RadyolojiApp.showHtmlReport('<orderId>')` — token kart onclick'inden alınır.
- **Model:** `RadiologyStudy{date, hospital, description, order_id}`.
- **Rapor:** `GetRaporByOrder {orderId}` → HTML → `radiology_report_text()` düz metne indirger.
- **Doğrulama (canlı):** birkaç çalışma, tüm alan dolu; rapor gövdesi düz metin.

---

## Randevular — sayfa tablosu `#tblRandevuListesi` (salt-okunur) ✅

- **Format:** `/Home/Randevularim` sayfasında sunucu-render tablo (ayrı liste
  endpoint'i yok). Kolonlar: **Tarih/Saat · Kurum · Klinik · Muayene Yeri · Hekim ·
  Durum · Randevu Türü · (İşlem)**.
- **Model:** `Appointment{date_time, institution, clinic, location, doctor, status, type}`.
- **Doğrulama (canlı):** birkaç randevu, tüm alan dolu; durum evreni `Aktif` / `Geçmiş`.
- **⚠️ Salt-okunur:** `/Randevu/*` aksiyon endpoint'leri (RandevuAl, RandevuIptal…)
  MEVCUT ama tool **kullanmaz** — sadece listeler.

---

## Faz 2 — Klinik çekirdek (canlı keşifle doğrulandı 2026-07-13) ✅

Çoğu alan **sunucu-render**: veri doğrudan `/Home/<Ad>` sayfasındaki `#tbl<Ad>`
tablosunda (ayrı AJAX yok). Kolon→alan eşlemesi (yapısal, PHI yok):

- **Alerjiler** — GET `/Home/Alerjilerim`, **3 tablo** (`#tblAlerjilerim`=ilaç,
  `#tblAlerjilerTanilarim`=tanı-bazlı, `#tblAlerjilerDeri`=deri testi). Kolonlar:
  Tarih · Alerji Türü · İlaç Adı · Belirtileri · (aksiyon×2).
  Model `Allergy{date, category, allergy_type, drug_name, symptoms}`.
- **Tanılar** — GET `/Home/Hastaliklarim` tablo `#tblHastaliklarim`. Kolonlar:
  Tarih · Tanı(ICD+ad) · Klinik · Hekim · (Detay). Detay: `HastalikDetayGoster(...,
  SysTakipNo)` → GET `/hastalik/GetHastalikDetay` (HTML → düz metin).
  Model `Diagnosis{date, diagnosis, clinic, doctor, sys_takip_no}`. **Canlı: onlarca kayıt.**
- **Kronik hastalık takibi** — GET `/Home/HastalikTakip` tablo `#tblHastalikTakip`.
  Kolonlar: Takip Tipi · Kronik Hastalık · Takip Tarihi · Planlanan Takip Tarihi ·
  Gerçekleşti mi? · (aksiyon). Detay: `HastalikTakipDetayGoster(sysTakipNo)` (POST HTML).
  Model `ChronicFollowup{followup_type, chronic_disease, followup_date, planned_date, realized, sys_takip_no}`.
- **Aşılar** — GET `/Home/AsiTakvimi` tablo `#tblAsilar` (detay yok, düz metin).
  Kolonlar: İşlem Zamanı · Yapılan Aşılar · Aşı Dozu · Aşı Yapılma Yeri.
  Model `Vaccination{date, vaccine, dose, location}`. **Canlı: birkaç kayıt.**
- **Epikrizler** — **POST** `/Epikriz/Index {baslangicYil, bitisYil}` tablo `#tblEpikriz`.
  Kolonlar: Tarih · Referans No · Hastane · Klinik · Hekim · (PDF).
  Model `DischargeSummary{date, reference_no, hospital, clinic, doctor, sys_no}`.
- **Patolojiler** — **POST** `/Patoloji/Index {baslangicYili, bitisYili}` ⚠️ (sonu "i")
  tablo `#tblPatoloji`, epikrizle aynı 6 kolon.
  Model `Pathology{date, reference_no, hospital, clinic, doctor, sys_no}`.

> **PDF detayları (Faz 4):** epikriz/patoloji satırındaki `PDFGetir(sysNo, referansNo)`
> → `/Epikriz/GetEpikrizPdf` · `/Patoloji/GetPatolojiPdf` (binary). Liste model'i `sys_no`+
> `reference_no`'yu bu çağrı için taşır.

## Faz 3 — Ziyaretler + Profil (canlı doğrulandı 2026-07-13) ✅

- **Hastane ziyaretleri (muayeneler)** — POST `/Ziyaret/Index {baslangicYil, bitisYil}`.
  Tablo/accordion DEĞİL: **kart ızgarası** `#ziyaretlerContainer > .ziyaretCardList`.
  Alanlar: `.zTarihS` (tarih) · `.card-text` (hastane) · `.drBrans` (klinik) ·
  `.drAdi` (hekim) · `.hastaneTakipNo` (takip no). Model `HospitalVisit{date, hospital,
  clinic, doctor, tracking_no}`. **Canlı: onlarca ziyaret.** Ziyaret detayı
  (`GetZiyaretDetay?data=<token>` — muayenedeki tahlil/reçete/tanı) lazy-load → Faz 3b.
- **Profil** — GET `/Home/ProfilBilgilerim` (veri sayfada; `KullaniciBilgileriniDoldur`
  "true" döner, kaynak değil). En temiz kaynak inline `var orgData = {Boy,Kilo,KanGrubu,...}`.
  Kan grubu kodu 1–8 → etiket. Kimlik kartı: `data-bs-original-title`. Model
  `Profile{full_name, birth_date, blood_type, height_cm, weight_kg, family_physician}`.
  **Gizlilik:** TCKN/e-posta/telefon çıktıya DAHİL DEĞİL. BMI/ölçüm-geçmişi YOK (sadece son değerler).

## Faz 3b — Tahlil trend + Ziyaret detayı (hedefli yakalamayla doğrulandı 2026-07-13) ✅

- **Tahlil trend** — GET `/Tahlil/TahlillerRapor {IslemTipi}`. `IslemTipi`, tahlil
  accordion'undaki `.karsilastirmaBtn onclick="GrafikGoster('<kod>')"`'dan gelir → artık
  `LabResult.trend_code` olarak döner. Yanıt tablo `#tbltahlilTablo`: **Tarih · Sonuç ·
  Sonuç Birimi · Referans Değeri**. Model `LabTrendPoint{date, value, unit, reference}`.
  **Canlı: birkaç nokta.**
- **Ziyaret detayı** — GET `/Ziyaret/GetZiyaretDetay?<qs>` (`qs`, ziyaret kartının
  "Detay Görüntüle" onclick'inden → `HospitalVisit.detail_ref`). Yanıt **4 tablo**:
  `#tblZiyaretlerimTani` (Tarih·Tanı·Hekim·Klinik), `#tblZiyaretlerimOnTani` (Ön Tanı),
  `#tblZiyaretlerimEkTani` (Ek Tanı), `#tblZiyaretlerimIslemler` (İşlem Zamanı·Randevu
  Zamanı·Adet·İşlem Adı). Model'ler `VisitDiagnosis` + `VisitProcedure`; parser dict döner
  (`diagnoses`/`preliminary_diagnoses`/`additional_diagnoses`/`procedures`). **Canlı: tanı ve işlem alanları dolu.**
- **⚠️ COVID DÜŞÜRÜLDÜ:** `POST /Tahlil/Index {activeTab: 1}` ayrı bir covid yapısı
  DÖNDÜRMÜYOR — yanıt normal tahlil accordion'u ile birebir aynı (1.240.294 vs 1.240.305 B,
  sıfır `tblTahlilCovid19`/`Covid19` işaretçisi). Covid sonuçları (varsa) normal
  `_list_lab_tests` accordion'unda görünür; ayrı tool gereksiz.

## Faz 4a — Reçete/ilaç HTML + dokümanlar (kolonlar sayfa thead'lerinden) ✅

- **Optik reçeteler** — POST `/Recete/GetOptikReceteler {baslangicYil, bitisYil}` →
  `#tbl-optikRecetelerim`. Kolonlar: Tarih · Reçete No · Reçete Türü · Hekim.
  Model `OpticalPrescription{date, prescription_no, type, doctor}`.
- **Tıbbi cihaz reçeteleri** — POST `/Recete/GetTibbiCihazReceteler {baslangicYil, bitisYil}` →
  `#tbl-tibbiCihazRecetelerim`. Kolonlar: Tarih · Reçete No · Hekim · Tesis Bilgisi.
  Model `DevicePrescription{date, prescription_no, doctor, facility}`.
- **İlaç prospektüsü** — POST `/Recete/GetIlacProspektusBilgisi {barcode, ilacName}` →
  serbest metin (`html_to_text`). `barcode`/`ilacName`, `enabiz_list_medications`'tan.
- **Dokümanlar** — GET `/Home/Dokumanlarim` → `#tblDokumanlarim` (Tarih · Başlık · aksiyon).
  Model `Document{date, title, bak_id}` (`bak_id`, `DokumanDetay('<bakId>')` onclick'inden).
  Detay = resim HTML (dosya değil), ileride ayrı tool.

> **Not:** Optik/cihaz/doküman satırları sayfada boş (POST/sunucu-render ile dolar) —
> kolonlar thead'den kesin; parser'lar sentetik fixture + canlı çağrıyla doğrulanır.

## Faz 4b — İlaç kullanım geçmişi + PDF/görüntü (canlı doğrulandı 2026-07-14) ✅

- **İlaç kullanım geçmişi** — POST `/Recete/GetIlacKullanimGecmisi {barcode}` →
  `#tbIlacGecmis` (8 kolon): Tarih · Barkod · İlaç Adı · İlaç Açıklaması · Kullanım Dozu ·
  Kullanım Sayısı · Kullanım Periyodu · Kullanım Şekli. Model `DrugUsage`. `barcode`,
  `enabiz_list_medications`'tan. Token/referer: `/Home/Recetelerim`. **Canlı: doğrulandı.**
- **Radyoloji rapor PDF** — POST `/RadyolojikGoruntu/GetRaporPdfByOrder {orderId}` →
  `application/json` `{rapor: <base64 PDF>}`. Tool base64→decode→diske kaydeder. `orderId`,
  `showHtmlReport` token'ı (rapor ile aynı). **Canlı: geçerli PDF.**
- **Radyoloji görüntü linki** — POST `/RadyolojikGoruntu/GetGoruntuLinkByOrder
  {AccessionNumber}` → `text/plain` DICOM viewer URL'i (binary değil). `AccessionNumber`,
  karttaki `openImageLink('<acc>')`'dan → `RadiologyStudy.accession_number` (yalnız görüntüsü
  olan çalışmalarda dolu; rapor `order_id`'sinden FARKLI id uzayı). **Canlı: http URL.**
- **Epikriz/Patoloji PDF** — düz GET `/Epikriz/GetEpikrizPdf` · `/Patoloji/GetPatolojiPdf`
  `{referansNo, sysNo}` → `application/pdf` bytes → diske. Model'ler `sys_no`+`reference_no`
  taşıyor (bu hesapta epikriz/patoloji 0 → canlı doğrulanamadı, mekanik lab/radyoloji ile aynı).

> **PDF stratejisi:** tüm PDF'ler `ENABIZ_DOWNLOAD_DIR`'e (varsayılan
> `~/.config/enabiz-mcp/downloads`, chmod 600) yazılır; tool içerik yerine
> `{saved_path, byte_size, sha256, content_type}` döner (PHI transkripte girmez).

## Faz 4c — Lab PDF (canlı doğrulandı 2026-07-14) ✅

- **Lab PDF** — GET `/Tahlil/TahlillerPdf {baslangicYil, bitisYil, cardTarih, kurumKodu,
  dil, sonucTuru}` → `application/pdf` bytes → diske. `cardTarih`+`kurumKodu`, tahlil
  accordion-item'ındaki `.pdfBtnSmall onclick="TahlillerPdfIndir('<dil>','<cardTarih>',
  '<kurumKodu>')"`'dan → `LabReport.card_tarih`/`kurum_kodu`. `dil` = `tr-TR`|`en-US`;
  **`sonucTuru=""` çalışır** (canlı doğrulandı: geçerli PDF). Tool `enabiz_get_lab_pdf`.
- **Cihaz reçete detay** — `POST /Recete/GetTibbiCihazReceteDetay {data: receteNo}` ⏸
  **blokeli:** bu hesapta cihaz reçetesi (0 kayıt) olmadığından `receteNo` alınamıyor →
  yanıt yapısı yakalanamıyor. Cihaz reçetesi mevcut olduğunda aynı desenle yazılabilir.

## Faz 5 — İdari alanlar (kolonlar sayfa thead'lerinden doğrulandı 2026-07-14) ✅

Hepsi sunucu-render GET-sayfa; bu hesapta 0 kayıt (kolonlar thead'den kesin).

- **Sigorta** — GET `/Home/Sigortalarim` → `#tblSigorta`: Açıklama · Sigorta Kodu ·
  Başlangıç-Bitiş Tarihleri · Bitiş Tarihi Ek Süre · Durum.
  Model `Insurance{description, insurance_code, date_range, extra_period, status}`.
- **Malzeme/cihaz** — GET `/Home/MalzemeveCihazlarim` → **5 kategori tablosu** (`...Diger`,
  `...Vucut`, `...Isitme`, `...Goz`, `...OzelYapim`), hepsi: İşlem Tarihi · Marka · Raf
  Ömrü · Ürün Tanımı. Model `MaterialDevice{date, category, brand, shelf_life, product}`.
- **Acil durum notları** — GET `/Home/AcilDurumNotlarim` → `#tblAcilDurum`: Tarih · Konu ·
  Açıklama. Model `EmergencyNote{date, subject, description}`.

## Kalan / ertelenen

- **Organ bağışı durumu** ⏸: `/Home/OrganBagisBeyan`'da temiz bir status tablosu/badge yok;
  gerçek durum `OrganBagisBeyanOnayDetay` (write/AJAX) ile yüklenir → salt-okunur temiz
  çıkarım belirsiz, ertelendi.
- **Cihaz reçete detay** ⏸: bu hesapta cihaz reçetesi yok (Faz 4c).
- **Faz 6:** canlı LLM-tool eval koşucusu, MCP istemci config örneği (README), opsiyonel
  `enabiz_get_health_summary`.
