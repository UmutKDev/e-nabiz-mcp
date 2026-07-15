# Bulgu: MHRS bundle keşif raporu (PHI-güvenli)

> Otomatik üretildi (`scripts/discover_mhrs.py`). Yalnız public statik JS okunarak çıkarıldı — **kimlik doğrulama YOK, `/api/`'ye istek YOK, PHI YOK**. Ham bundle `docs/findings/raw/mhrs/`'de (gitignored).

**Özet:** build_version: 2.1.405 · chunks_read: 87 · source: kayıtlı bundle (--from-raw) · endpoints: 161 · read: 75 · write: 74 · unknown: 12

> ⚠️ **Yazma uçları aşağıda LİSTELENİR ama keşif tarayıcısı tarafından ASLA çağrılmaz.** Belgelemek çağırmak değildir. MHRS 12 ucu GET ile yazar (`iptal-et`, `geri-al`, `ayni-hekimden-randevu-al`), bu yüzden HTTP metodu güvenlik sinyali olarak kullanılamaz — sınıflama ad-bazlıdır.

| Method | Yol (route şablonu) | Verdict | Kaynak |
|---|---|---|---|
| POST | `kurum-rss/randevu/slot-sorgulama/arama` | read | chunk-45 |
| POST | `kurum-rss/randevu/slot-sorgulama/slot` | read | chunk-45 |
| GET | `kurum/genel-arama` | read | chunk-45 |
| GET | `kurum/hekim/hekim-klinik/hekim-select-input/anakurum/{p1}/kurum/{p2}/klinik/{p3}` | read | chunk-18 |
| GET | `kurum/hekim/hekim-klinik/sorgula-by-hekim` | read | chunk-35 |
| GET | `kurum/hekim/hekim-klinik/sorgula-by-hekim?mhrsHekimId={p1}&mhrsKlinikId={p2}` | read | chunk-27 |
| GET | `kurum/kurum/ah-hekim-kurum/ahb/mhrs-ah-kurum-id/{p1}` | unknown | chunk-45 |
| POST | `kurum/kurum/duyuru-kurum/goster` | 🔴 write | chunk-45 |
| GET | `kurum/kurum/kurum-bilgileri/asm-ana-kurum/{p1}` | read | chunk-7 |
| GET | `kurum/kurum/kurum-bilgileri/en-yakin` | read | chunk-45 |
| GET | `kurum/kurum/kurum-bilgileri/en-yakin-aile-hekimi` | read | chunk-45 |
| GET | `kurum/kurum/kurum-bilgileri/en-yakin-by-klinik` | read | chunk-45 |
| GET | `kurum/kurum/kurum-bilgileri/kurum-info/` | read | chunk-18 |
| GET | `kurum/kurum/kurum-bilgileri/kurum-info/{p1}` | read | chunk-7 |
| GET | `kurum/kurum/kurum-klinik/il/-1/ilce/-1/kurum/{p1}/klinik/-1/ana-kurum/select-input` | read | chunk-18 |
| GET | `kurum/kurum/kurum-klinik/il/{p1}/ilce/{p2}/kurum/{p3}/aksiyon/{p4}/randevuTuru/{p5}/select-input` | read | chunk-18 |
| GET | `kurum/kurum/kurum-klinik/il/{p1}/ilce/{p2}/kurum/{p3}/klinik/{p4}/ana-kurum/select-input` | read | chunk-18 |
| GET | `kurum/kurum/kurum-klinik/klinik/select-input` | read | chunk-45 |
| GET | `kurum/kurum/kurum/asm/mhrs-il-id/{p1}/mhrs-ilce-id/{p2}` | unknown | chunk-45 |
| GET | `kurum/kurum/muayene-yeri/ana-kurum/-1/kurum/{p1}/klinik/{p2}/select-input` | read | chunk-27 |
| GET | `kurum/kurum/muayene-yeri/ana-kurum/{p1}/kurum/{p2}/klinik/{p3}/select-input` | read | chunk-18 |
| GET | `kurum/randevu-arsiv/randevu-arsiv` | read | chunk-39 |
| POST | `kurum/randevu-notlari` | 🔴 write | chunk-27 |
| PUT | `kurum/randevu-notlari` | 🔴 write | chunk-27 |
| DELETE | `kurum/randevu-notlari/by-hrn/{p1}` | 🔴 write | chunk-27 |
| GET | `kurum/randevu-ozellik/gizle/{p1}` | 🔴 write | chunk-7 |
| GET | `kurum/randevu-ozellik/gizlilik-kaldir/{p1}` | 🔴 write | chunk-27 |
| POST | `kurum/randevu-talep` | 🔴 write | chunk-45 |
| GET | `kurum/randevu-talep/bilgilendir/{p1}` | 🔴 write | chunk-37 |
| GET | `kurum/randevu-talep/search` | read | chunk-37 |
| POST | `kurum/randevu-talep/yenile/{p1}` | 🔴 write | chunk-37 |
| DELETE | `kurum/randevu-talep/{p1}` | 🔴 write | chunk-37 |
| GET | `kurum/randevu-turu/grup` | read | chunk-45 |
| GET | `kurum/randevu/aksiyon/by-basmak-grubu/{p1}` | unknown | chunk-45 |
| GET | `kurum/randevu/ayni-hekimden-randevu-al/{p1}` | 🔴 write | chunk-27 |
| POST | `kurum/randevu/cakisma-okundu` | 🔴 write | chunk-45 |
| GET | `kurum/randevu/cakisma-onay/{p1}` | 🔴 write | chunk-27 |
| POST | `kurum/randevu/degisikligi-istisna-okundu` | 🔴 write | chunk-45 |
| GET | `kurum/randevu/degisikligi-istisna-onayla/{p1}` | 🔴 write | chunk-27 |
| GET | `kurum/randevu/degisikligi-istisna-reddet/{p1}` | 🔴 write | chunk-27 |
| POST | `kurum/randevu/degisikligi-okundu` | 🔴 write | chunk-45 |
| GET | `kurum/randevu/degisikligi-onayla/{p1}` | 🔴 write | chunk-27 |
| GET | `kurum/randevu/degisikligi-reddet/{p1}` | 🔴 write | chunk-27 |
| GET | `kurum/randevu/geri-al/{p1}` | 🔴 write | chunk-27 |
| GET | `kurum/randevu/iptal-et-hrn-uuid/{p1}/{p2}` | 🔴 write | chunk-54 |
| GET | `kurum/randevu/iptal-et/{p1}` | 🔴 write | chunk-27 |
| GET | `kurum/randevu/muayene-yeri-degisiklik-getir/{p1}/{p2}` | read | chunk-60 |
| POST | `kurum/randevu/randevu-ekle` | 🔴 write | chunk-10 |
| GET | `kurum/randevu/randevu-gecmisi` | read | chunk-27 |
| GET | `kurum/randevu/randevu-gizleme-uyari/{p1}` | read | chunk-7 |
| POST | `kurum/randevu/randevu-iptal-et-yeni-al` | 🔴 write | chunk-10 |
| GET | `kurum/randevu/randevu-iptal-uyari/{p1}` | 🔴 write | chunk-27 |
| POST | `kurum/randevu/randevu-talep-eslesme-red/{p1}` | 🔴 write | chunk-85 |
| DELETE | `kurum/randevu/slot-kilitleme` | 🔴 write | chunk-10 |
| GET | `kurum/randevu/slot-sorgulama/en-gec-gun/by-aksiyon-klinik?aksiyonId={p1}&mhrsKlinikId={p2}` | read | chunk-18 |
| GET | `kurum/randevu/slot-sorgulama/en-gec-gun/by-aksiyon?aksiyonId={p1}` | read | chunk-18 |
| GET | `kurum/randevu/slot-sorgulama/randevu-bilgileri?fkSlotId={p1}` | read | chunk-10 |
| GET | `kurum/randevu/yaklasan-randevularim` | read | chunk-45 |
| POST | `kurum/rapor/bashekim-sms-rapor-detay/{p1}/` | 🔴 write | chunk-84 |
| GET | `vatandas/aydinlatma-metni` | unknown | chunk-45 |
| GET | `vatandas/aydinlatma-metni/gizlilik-politikasi` | unknown | chunk-61 |
| GET | `vatandas/bildirim/iletisim-kontrol` | read | chunk-45 |
| GET | `vatandas/bildirim/login-uyari` | read | chunk-45 |
| GET | `vatandas/dil` | read | main |
| PUT | `vatandas/dil/dil-bilgileri/{p1}` | 🔴 write | main |
| POST | `vatandas/edevlet/after-login` | 🔴 write | main |
| POST | `vatandas/edevlet/login` | 🔴 write | main |
| GET | `vatandas/edevlet/login-url` | unknown | main |
| POST | `vatandas/enabiz/after-login` | 🔴 write | main |
| POST | `vatandas/enabiz/login` | 🔴 write | main |
| GET | `vatandas/enabiz/randevu-tekrarla` | 🔴 write | chunk-45 |
| GET | `vatandas/favori` | read | chunk-35 |
| PUT | `vatandas/favori/ekle` | 🔴 write | chunk-10 |
| PUT | `vatandas/favori/en-ustte/{p1}` | 🔴 write | chunk-35 |
| DELETE | `vatandas/favori/{p1}` | 🔴 write | chunk-35 |
| GET | `vatandas/gizlilik-politikalari` | unknown | chunk-38 |
| GET | `vatandas/hesap-bilgileri/bilgilendirme-tercihleri` | read | chunk-28 |
| PUT | `vatandas/hesap-bilgileri/bilgilendirme-tercihleri` | 🔴 write | chunk-28 |
| GET | `vatandas/hesap-bilgileri/guvenlik-resimleri` | read | chunk-20 |
| POST | `vatandas/hesap-bilgileri/guvenlik-soru-resim` | 🔴 write | chunk-23 |
| GET | `vatandas/hesap-bilgileri/kullanici-temasi` | read | main |
| PUT | `vatandas/hesap-bilgileri/parola-degistir` | 🔴 write | chunk-31 |
| GET | `vatandas/hesap-bilgileri/son-giris-bilgileri` | read | chunk-32 |
| GET | `vatandas/hesap-bilgileri/tema-bilgileri` | read | chunk-12 |
| PUT | `vatandas/hesap-bilgileri/tema-dil-bilgileri/{p1}/` | 🔴 write | chunk-45 |
| PUT | `vatandas/hesap-bilgileri/tema-dil-bilgileri/{p1}/{p2}` | 🔴 write | chunk-12 |
| POST | `vatandas/iki-asamali-giris/sms-dogrulama-key-onay` | 🔴 write | chunk-47 |
| POST | `vatandas/iletisim/dogrulama/gonder` | 🔴 write | chunk-21 |
| POST | `vatandas/iletisim/dogrulama/yap` | 🔴 write | chunk-21 |
| POST | `vatandas/iletisim/eposta` | 🔴 write | chunk-14 |
| PUT | `vatandas/iletisim/eposta` | 🔴 write | chunk-14 |
| GET | `vatandas/iletisim/eposta/aktif` | read | chunk-20 |
| POST | `vatandas/iletisim/eposta/birincil-yap/{p1}` | 🔴 write | chunk-14 |
| GET | `vatandas/iletisim/eposta/ekleyebilir-mi` | read | chunk-21 |
| POST | `vatandas/iletisim/eposta/kilitle-by-uuid/{p1}/{p2}` | 🔴 write | chunk-53 |
| DELETE | `vatandas/iletisim/eposta/{p1}` | 🔴 write | chunk-14 |
| POST | `vatandas/iletisim/telefon` | 🔴 write | chunk-11 |
| PUT | `vatandas/iletisim/telefon` | 🔴 write | chunk-11 |
| GET | `vatandas/iletisim/telefon/aktif` | read | chunk-20 |
| POST | `vatandas/iletisim/telefon/birincil-yap/{p1}` | 🔴 write | chunk-11 |
| GET | `vatandas/iletisim/telefon/ekleyebilir-mi` | read | chunk-21 |
| POST | `vatandas/iletisim/telefon/guncellemeKontrol` | 🔴 write | chunk-11 |
| DELETE | `vatandas/iletisim/telefon/{p1}` | 🔴 write | chunk-11 |
| GET | `vatandas/kimlik-bilgileri` | read | chunk-30 |
| POST | `vatandas/kimlik-bilgileri/guncelle-mernis` | 🔴 write | chunk-30 |
| POST | `vatandas/login/v2` | 🔴 write | main |
| POST | `vatandas/logout` | 🔴 write | main |
| GET | `vatandas/menu` | read | chunk-45 |
| POST | `vatandas/neyim-var/after-login` | 🔴 write | main |
| POST | `vatandas/neyim-var/login` | 🔴 write | main |
| POST | `vatandas/parola-sifirlama/sms` | 🔴 write | chunk-24 |
| POST | `vatandas/parola-sifirlama/sms-dogrulama-key-gonder` | 🔴 write | chunk-24 |
| POST | `vatandas/parola-sifirlama/sms-dogrulama-key-onay` | 🔴 write | chunk-24 |
| GET | `vatandas/portal/anket/sikca-sorulan-sorular` | read | chunk-13 |
| POST | `vatandas/uyelik` | 🔴 write | chunk-15 |
| POST | `vatandas/uyelik/cep-tel-dogrulama-gonder` | 🔴 write | chunk-20 |
| POST | `vatandas/uyelik/cep-tel-dogrulama-yap` | 🔴 write | chunk-20 |
| PUT | `vatandas/uyelik/gizlilik-politikasi-onay/{p1}` | 🔴 write | chunk-45 |
| GET | `vatandas/uyelik/guvenlik-tercihi` | unknown | chunk-29 |
| PUT | `vatandas/uyelik/guvenlik-tercihi` | 🔴 write | chunk-29 |
| POST | `vatandas/uyelik/iletisim-ve-guvenlik-bilgileri-kaydet` | 🔴 write | chunk-20 |
| POST | `vatandas/uyelik/kontrol` | 🔴 write | chunk-15 |
| GET | `vatandas/uyelik/mhrs-vatandas-login-aktif` | read | chunk-47 |
| POST | `vatandas/uyelik/sms-eposta-ile-sil` | 🔴 write | chunk-55 |
| GET | `vatandas/vatandas/aile-dis-hekimi` | unknown | chunk-45 |
| GET | `vatandas/vatandas/aile-hekimi` | unknown | chunk-10 |
| GET | `vatandas/vatandas/hasta-bilgisi` | read | chunk-45 |
| POST | `vatandas/vatandas/hesabima-don` | 🔴 write | chunk-45 |
| POST | `vatandas/vatandas/soru-gorus-bildirim/kaydet` | 🔴 write | chunk-45 |
| GET | `vatandas/vatandas/soru-gorus-konu` | unknown | chunk-45 |
| POST | `vatandas/vatandas/yetkili-hesaba-gec` | 🔴 write | chunk-33 |
| GET | `vatandas/vatandas/yetkili-kisiler` | unknown | chunk-33 |
| GET | `yonetim/genel/il/selectinput-tree` | read | chunk-18 |
| GET | `yonetim/genel/il/selectinput-tree-neyim` | read | chunk-18 |
| GET | `yonetim/genel/ilce/selectinput/{p1}` | read | chunk-18 |
| GET | `yonetim/genel/lookup/selectinput/CINSIYET` | read | chunk-38 |
| GET | `yonetim/genel/lookup/selectinput/EPOSTA_TIPI` | read | chunk-20 |
| GET | `yonetim/genel/lookup/selectinput/HATIRLATMA_SAAT_SECIMI` | read | chunk-45 |
| GET | `yonetim/genel/lookup/selectinput/RANDEVU_ZAMANI_FILTER` | read | chunk-45 |
| GET | `yonetim/genel/lookup/selectinput/TELEFON_TIPI` | read | chunk-21 |
| GET | `yonetim/genel/lookup/selectinput/UYELIK_TELEFON_TIPI` | read | chunk-20 |
| GET | `yonetim/genel/lookup/selectinput/VATANDAS_SORU` | read | chunk-20 |
| GET | `yonetim/genel/mesaj/by-kodu/GNL1020` | read | chunk-85 |
| GET | `yonetim/genel/mesaj/by-kodu/GNL2016` | read | chunk-45 |
| GET | `yonetim/genel/mesaj/by-kodu/GNL2030` | read | chunk-45 |
| GET | `yonetim/genel/mesaj/by-kodu/RND4105` | read | chunk-35 |
| GET | `yonetim/genel/mesaj/by-kodu/RND6041` | read | chunk-27 |
| GET | `yonetim/genel/mesaj/by-kodu/RND6042` | read | chunk-27 |
| GET | `yonetim/genel/mesaj/by-kodu/RNDG1000` | read | chunk-27 |
| GET | `yonetim/genel/mesaj/by-kodu/RNDG1001` | read | chunk-27 |
| GET | `yonetim/genel/mesaj/by-kodu/RNDI1003` | read | chunk-45 |
| GET | `yonetim/genel/mesaj/by-kodu/RNDNEY1000` | read | chunk-45 |
| GET | `yonetim/genel/mesaj/by-kodu/VTP1002` | read | chunk-20 |
| GET | `yonetim/genel/parametre/degeri/KURUM_SECIMI_ZORUNLU_ILLER` | read | chunk-18 |
| GET | `yonetim/genel/parametre/degeri/RANDEVU_SAATINDEN_ONCE_GERCEKLESME` | read | chunk-7 |
| GET | `yonetim/genel/parametre/degeri/RIS_HASTANE_LISTESI_ADIMI` | read | chunk-45 |
| GET | `yonetim/genel/parametre/degeri/RIS_RANDEVU_AL_ADIMI` | read | chunk-45 |
| GET | `yonetim/genel/parametre/degeri/RIS_RANDEVU_ARA_ADIMI` | read | chunk-45 |
| GET | `yonetim/genel/parametre/degeri/RIS_RANDEVU_ONAYLA_ADIMI` | read | chunk-10 |
| GET | `yonetim/genel/parametre/degeri/SLOT_LISTELEME_MAX_GUN_WEB` | read | chunk-45 |
| GET | `yonetim/genel/parametre/degeri/UYE_OL_BUTON_GORUNURLUK` | read | chunk-47 |

## Yazma uçları (74) — tool ÇAĞIRMAZ

- `POST kurum/kurum/duyuru-kurum/goster`
- `POST kurum/randevu-notlari`
- `PUT kurum/randevu-notlari`
- `DELETE kurum/randevu-notlari/by-hrn/{p1}`
- `GET kurum/randevu-ozellik/gizle/{p1}`
- `GET kurum/randevu-ozellik/gizlilik-kaldir/{p1}`
- `POST kurum/randevu-talep`
- `GET kurum/randevu-talep/bilgilendir/{p1}`
- `POST kurum/randevu-talep/yenile/{p1}`
- `DELETE kurum/randevu-talep/{p1}`
- `GET kurum/randevu/ayni-hekimden-randevu-al/{p1}`
- `POST kurum/randevu/cakisma-okundu`
- `GET kurum/randevu/cakisma-onay/{p1}`
- `POST kurum/randevu/degisikligi-istisna-okundu`
- `GET kurum/randevu/degisikligi-istisna-onayla/{p1}`
- `GET kurum/randevu/degisikligi-istisna-reddet/{p1}`
- `POST kurum/randevu/degisikligi-okundu`
- `GET kurum/randevu/degisikligi-onayla/{p1}`
- `GET kurum/randevu/degisikligi-reddet/{p1}`
- `GET kurum/randevu/geri-al/{p1}`
- `GET kurum/randevu/iptal-et-hrn-uuid/{p1}/{p2}`
- `GET kurum/randevu/iptal-et/{p1}`
- `POST kurum/randevu/randevu-ekle`
- `POST kurum/randevu/randevu-iptal-et-yeni-al`
- `GET kurum/randevu/randevu-iptal-uyari/{p1}`
- `POST kurum/randevu/randevu-talep-eslesme-red/{p1}`
- `DELETE kurum/randevu/slot-kilitleme`
- `POST kurum/rapor/bashekim-sms-rapor-detay/{p1}/`
- `PUT vatandas/dil/dil-bilgileri/{p1}`
- `POST vatandas/edevlet/after-login`
- `POST vatandas/edevlet/login`
- `POST vatandas/enabiz/after-login`
- `POST vatandas/enabiz/login`
- `GET vatandas/enabiz/randevu-tekrarla`
- `PUT vatandas/favori/ekle`
- `PUT vatandas/favori/en-ustte/{p1}`
- `DELETE vatandas/favori/{p1}`
- `PUT vatandas/hesap-bilgileri/bilgilendirme-tercihleri`
- `POST vatandas/hesap-bilgileri/guvenlik-soru-resim`
- `PUT vatandas/hesap-bilgileri/parola-degistir`
- `PUT vatandas/hesap-bilgileri/tema-dil-bilgileri/{p1}/`
- `PUT vatandas/hesap-bilgileri/tema-dil-bilgileri/{p1}/{p2}`
- `POST vatandas/iki-asamali-giris/sms-dogrulama-key-onay`
- `POST vatandas/iletisim/dogrulama/gonder`
- `POST vatandas/iletisim/dogrulama/yap`
- `POST vatandas/iletisim/eposta`
- `PUT vatandas/iletisim/eposta`
- `POST vatandas/iletisim/eposta/birincil-yap/{p1}`
- `POST vatandas/iletisim/eposta/kilitle-by-uuid/{p1}/{p2}`
- `DELETE vatandas/iletisim/eposta/{p1}`
- `PUT vatandas/iletisim/telefon`
- `POST vatandas/iletisim/telefon`
- `POST vatandas/iletisim/telefon/birincil-yap/{p1}`
- `POST vatandas/iletisim/telefon/guncellemeKontrol`
- `DELETE vatandas/iletisim/telefon/{p1}`
- `POST vatandas/kimlik-bilgileri/guncelle-mernis`
- `POST vatandas/login/v2`
- `POST vatandas/logout`
- `POST vatandas/neyim-var/after-login`
- `POST vatandas/neyim-var/login`
- `POST vatandas/parola-sifirlama/sms`
- `POST vatandas/parola-sifirlama/sms-dogrulama-key-gonder`
- `POST vatandas/parola-sifirlama/sms-dogrulama-key-onay`
- `POST vatandas/uyelik`
- `POST vatandas/uyelik/cep-tel-dogrulama-gonder`
- `POST vatandas/uyelik/cep-tel-dogrulama-yap`
- `PUT vatandas/uyelik/gizlilik-politikasi-onay/{p1}`
- `PUT vatandas/uyelik/guvenlik-tercihi`
- `POST vatandas/uyelik/iletisim-ve-guvenlik-bilgileri-kaydet`
- `POST vatandas/uyelik/kontrol`
- `POST vatandas/uyelik/sms-eposta-ile-sil`
- `POST vatandas/vatandas/hesabima-don`
- `POST vatandas/vatandas/soru-gorus-bildirim/kaydet`
- `POST vatandas/vatandas/yetkili-hesaba-gec`
