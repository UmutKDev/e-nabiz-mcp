# Bulgu: Keşif taraması raporu (PHI-güvenli)

> Otomatik üretildi (`scripts/discover.py`). Yalnız API SÖZLEŞMESİ içerir — hasta değeri YOK, **kayıt sayısı/yanıt boyutu gibi veri-bağımlı nicelik de YOK** (bunlar kullanıcının verisinin fonksiyonudur). Ham HTML `docs/findings/raw/`'da (gitignored).

**Özet:** pages_scanned: 14 · endpoints_found: 124 · replayed_read: 21 · skipped: 103 · year_range: 2021-2026 · mode: replay

| Sayfa | Uç | Method | Param adları | HTTP | Container | Verdict |
|---|---|---|---|---|---|---|
| /Home/Alerjilerim | /Home/Alerjilerim | GET | — | 200 | #tblAlerjilerim | page(server-render) |
| /Home/Alerjilerim | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/Alerjilerim | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/Alerjilerim | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/Alerjilerim | /Alerji/AlerjiEkleGoruntule | POST | — | — | #divAlerjiEkle | not-read(write) |
| /Home/Alerjilerim | /Alerji/AlerjiSil | POST | id | — | #AlerjiSilModal | not-read(write) |
| /Home/Alerjilerim | /Alerji/AlerjiDuzenleGoruntule | POST | alerjiId | — | #divAlerjiDuzenle | not-read(write) |
| /Home/Alerjilerim | /Alerji/AlerjiSilGoruntule | POST | id | — | #divSil | not-read(write) |
| /Home/Alerjilerim | /HizliErisim/Index | GET | key | — | — | needs-id:key |
| /Home/Hastaliklarim | /Home/Hastaliklarim | GET | — | 200 | #tblHastaliklarim | page(server-render) |
| /Home/Hastaliklarim | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/Hastaliklarim | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/Hastaliklarim | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/Hastaliklarim | /Hastalik/Index | POST | baslangicYili, bitisYili | — | #tblHastaliklarim | needs-id:baslangicYili |
| /Home/Hastaliklarim | /HizliErisim/Index | GET | key | — | — | needs-id:key |
| /Home/HastalikTakip | /Home/HastalikTakip | GET | — | 200 | #tblHastalikTakip | page(server-render) |
| /Home/HastalikTakip | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/HastalikTakip | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/HastalikTakip | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/HastalikTakip | /HastalikTakip/detay | POST | — | 200 | #hastalikTakipDetay | read |
| /Home/HastalikTakip | /HizliErisim/Index | GET | key | — | — | needs-id:key |
| /Home/AsiTakvimi | /Home/AsiTakvimi | GET | — | 200 | #tblAsilar | page(server-render) |
| /Home/AsiTakvimi | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/AsiTakvimi | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/AsiTakvimi | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/AsiTakvimi | /HizliErisim/Index | GET | key | — | — | needs-id:key |
| /Home/Epikrizlerim | /Home/Epikrizlerim | GET | — | 200 | #tblEpikriz | page(server-render) |
| /Home/Epikrizlerim | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/Epikrizlerim | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/Epikrizlerim | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/Epikrizlerim | /Epikriz/Index | POST | baslangicYil, bitisYil | 200 | #tblEpikriz | read |
| /Home/Epikrizlerim | /HizliErisim/Index | GET | key | — | — | needs-id:key |
| /Home/Patolojilerim | /Home/Patolojilerim | GET | — | 200 | #tblPatoloji | page(server-render) |
| /Home/Patolojilerim | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/Patolojilerim | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/Patolojilerim | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/Patolojilerim | /Patoloji/Index | POST | baslangicYili, bitisYili | — | #tblPatoloji | needs-id:baslangicYili |
| /Home/Patolojilerim | /HizliErisim/Index | GET | key | — | — | needs-id:key |
| /Home/Ziyaretlerim | /Home/Ziyaretlerim | GET | — | 200 | — | page |
| /Home/Ziyaretlerim | /Ziyaret/HastaneDegerlendir | GET | bilgi | — | #iYorum | not-read(write) |
| /Home/Ziyaretlerim | /Paylasim/GeciciPaylasimDuzenle | POST | — | — | #geciciPaylasimDuzenleModal | not-read(write) |
| /Home/Ziyaretlerim | /Ziyaret/ZiyaretGizle | POST | sysTakipNo, ziyaret | — | — | not-read(write) |
| /Home/Ziyaretlerim | /Ziyaret/PostOnayOTPGonder | POST | — | — | — | not-read(write) |
| /Home/Ziyaretlerim | /Ziyaret/PostOnayOTPKontrol | POST | kod | — | — | not-read(unknown) |
| /Home/Ziyaretlerim | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/Ziyaretlerim | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/Ziyaretlerim | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/Ziyaretlerim | /Ziyaret/Index | POST | baslangicYil, bitisYil | 200 | #dvZiyaretDetay | read |
| /Home/Ziyaretlerim | /Paylasim/GeciciPaylasimlar | GET | __RequestVerificationToken | — | #paylasim | not-read(unknown) |
| /Home/Ziyaretlerim | /Ziyaret/GetHastaneDegerlendirme | GET | __RequestVerificationToken | — | — | not-read(write) |
| /Home/Ziyaretlerim | /Ziyaret/ZiyaretiPaylasimdaGizle | POST | — | — | — | not-read(write) |
| /Home/Ziyaretlerim | /Ziyaret/ZiyaretiPaylasimdaGoster | POST | — | — | — | not-read(unknown) |
| /Home/Ziyaretlerim | /Ziyaret/ZiyaretNotuGoruntule | POST | SYSTakipNo, HastaneAdi, BransAdi, Hekim, Not, HatirlatmaTarihi | — | #ziyaretNotu | not-read(unknown) |
| /Home/Ziyaretlerim | /Ziyaret/HastaneyeHataBildir | GET | tarih, SYSTakipNo, islemKodu, islemAdi, hastane | — | — | not-read(unknown) |
| /Home/Ziyaretlerim | /HizliErisim/Index | GET | key | — | — | needs-id:key |
| /Home/Dokumanlarim | /Home/Dokumanlarim | GET | — | 200 | #tblDokumanlarim | page(server-render) |
| /Home/Dokumanlarim | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/Dokumanlarim | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/Dokumanlarim | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/Dokumanlarim | /Dokuman/DokumanEkleGoruntule | POST | — | — | #divDokumanEkle | not-read(write) |
| /Home/Dokumanlarim | /Dokuman/DokumanSil | POST | bakId | — | #DokumanSilModal | not-read(write) |
| /Home/Dokumanlarim | /Dokuman/DokumanDetayGetir | POST | bakId | — | #divFoto | needs-id:bakId |
| /Home/Dokumanlarim | /Dokuman/DokumanSilGoruntule | POST | bakId | — | #divSil | not-read(write) |
| /Home/Dokumanlarim | /HizliErisim/Index | GET | key | — | — | needs-id:key |
| /Home/MalzemeveCihazlarim | /Home/MalzemeveCihazlarim | GET | — | 200 | #tblMalzemeVeCihazlarimDiger | page(server-render) |
| /Home/MalzemeveCihazlarim | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/MalzemeveCihazlarim | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/MalzemeveCihazlarim | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/MalzemeveCihazlarim | /HizliErisim/Index | GET | key | — | — | needs-id:key |
| /Home/Sigortalarim | /Home/Sigortalarim | GET | — | 200 | #tblSigorta | page(server-render) |
| /Home/Sigortalarim | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/Sigortalarim | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/Sigortalarim | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/Sigortalarim | /Sigorta/SigortaKoduOlusturGoruntule | POST | — | — | #divSigortaPaylasim | not-read(unknown) |
| /Home/Sigortalarim | /Sigorta/SigortaKoduOlustur | POST | Aciklama, BaslangicTarihi, BitisTarihi, EkSure, SigortaKodu | — | #SigortaPaylasimEkleModal | not-read(unknown) |
| /Home/Sigortalarim | /Sigorta/SigortaPaylasimSilOnayGoruntule | POST | silmeUyari | — | #uyariAlani | not-read(write) |
| /Home/Sigortalarim | /Sigorta/SigortaPaylasimSil | POST | sigortaKodu | — | #SigortaPaylasimSilModal | not-read(write) |
| /Home/Sigortalarim | /Sigorta/SigortaKoduAktiflestirGoruntule | POST | sigortaKoduAciklama, baslangicTarihiAciklama, bitisTarihiAciklama, ekSureAciklama, aciklama, baslangicTarihi, bitisTarihi, ekSure | — | #divSigortaPaylasimAktf | not-read(unknown) |
| /Home/Sigortalarim | /HizliErisim/Index | GET | key | — | — | needs-id:key |
| /Home/ProfilBilgilerim | /Home/ProfilBilgilerim | GET | — | 200 | — | page |
| /Home/ProfilBilgilerim | /Profil/ProfilTelefonBirincilYap | POST | id | — | — | not-read(unknown) |
| /Home/ProfilBilgilerim | /Profil/ProfilTelefonSil | POST | id | — | — | not-read(write) |
| /Home/ProfilBilgilerim | /Profil/ProfilEpostaBirincilYap | POST | id | — | — | not-read(unknown) |
| /Home/ProfilBilgilerim | /Profil/ProfilEpostaSil | POST | id | — | — | not-read(write) |
| /Home/ProfilBilgilerim | /Profil/ProfilAcilDurumTelefonSil | POST | id | — | — | not-read(write) |
| /Home/ProfilBilgilerim | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/ProfilBilgilerim | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/ProfilBilgilerim | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/ProfilBilgilerim | /Profil/KisiBilgileriGuncelle | GET | — | — | — | not-read(write) |
| /Home/ProfilBilgilerim | /Profil/TelefonOnayla | POST | telNo, isAcilKisi | — | #profilYeniEkleModal | not-read(write) |
| /Home/ProfilBilgilerim | /Profil/TelefonOnayKontrol | POST | cepTelefonu, kod, acilDurum | — | — | not-read(unknown) |
| /Home/ProfilBilgilerim | /Profil/EmailOnayla | POST | toEmail | — | #profilYeniEkleModal | not-read(write) |
| /Home/ProfilBilgilerim | /Profil/EpostaOnayKontrol | POST | eposta, kod | — | — | not-read(unknown) |
| /Home/ProfilBilgilerim | /Profil/ProfilResmiSil | POST | — | — | — | not-read(write) |
| /Home/ProfilBilgilerim | /HizliErisim/Index | GET | key | — | — | needs-id:key |
| /Home/AcilDurumNotlarim | /Home/AcilDurumNotlarim | GET | — | 200 | #tblAcilDurum | page(server-render) |
| /Home/AcilDurumNotlarim | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/AcilDurumNotlarim | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/AcilDurumNotlarim | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/AcilDurumNotlarim | /AcilDurum/AcilDurumNotuSil | POST | id | — | #AcilDurumSilModal | not-read(write) |
| /Home/AcilDurumNotlarim | /AcilDurum/AcilDurumNotuEkleGoruntule | POST | — | — | #divAcilDurumNotuEkle | not-read(write) |
| /Home/AcilDurumNotlarim | /AcilDurum/AcilDurumNotuDuzenleGoruntule | POST | acilDurumId | — | #divAcilDurumNotuDuzenle | not-read(write) |
| /Home/AcilDurumNotlarim | /AcilDurum/AcilDurumNotuSilGoruntule | POST | id | — | #divSil | not-read(write) |
| /Home/AcilDurumNotlarim | /HizliErisim/Index | GET | key | — | — | needs-id:key |
| /Home/OrganBagisBeyan | /Home/OrganBagisBeyan | GET | — | 200 | — | page |
| /Home/OrganBagisBeyan | /OrganBagisBeyan/OrganBagisBeyanOnayDetay | GET | — | — | #organBagisBeyanBody | not-read(write) |
| /Home/OrganBagisBeyan | /OrganBagisBeyan/OrganBagisYakinDogrula | POST | — | — | — | not-read(unknown) |
| /Home/OrganBagisBeyan | /OrganBagisBeyan/PostOnayOTPGonder | POST | — | — | — | not-read(write) |
| /Home/OrganBagisBeyan | /OrganBagisBeyan/PostOnayOTPKontrol | POST | kod | — | — | not-read(unknown) |
| /Home/OrganBagisBeyan | /OrganBagisBeyan/OrganBagisBeyanOnayla | POST | — | — | — | not-read(write) |
| /Home/OrganBagisBeyan | /OrganBagisBeyan/PostIptalOTPGonder | POST | — | — | — | not-read(write) |
| /Home/OrganBagisBeyan | /OrganBagisBeyan/PostIptalOTPKontrol | POST | kod | — | — | not-read(write) |
| /Home/OrganBagisBeyan | /OrganBagisBeyan/OrganBagisBeyanIptalEt | POST | — | — | — | not-read(write) |
| /Home/OrganBagisBeyan | /OrganBagisBeyan/PostYakinBildirimiProfilimdeGizle | POST | — | — | — | not-read(write) |
| /Home/OrganBagisBeyan | /OrganBagisBeyan/PostYakinTelefonuGetir | POST | — | 403 | — | read |
| /Home/OrganBagisBeyan | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/OrganBagisBeyan | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/OrganBagisBeyan | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/OrganBagisBeyan | /HizliErisim/Index | GET | key | — | — | needs-id:key |
| /Home/Index | /Home/Index | GET | — | 200 | — | page |
| /Home/Index | /Home/Favoriler | POST | __RequestVerificationToken, type | — | #favorileBtn | needs-id:type |
| /Home/Index | /Profil/CocuklarimiGoremiyorum | GET | — | — | — | not-read(unknown) |
| /Home/Index | /Profil/KullaniciBilgileriniDoldur | GET | — | 200 | — | read |
| /Home/Index | /Profil/KiloBoyGuncelle | POST | boy, kilo | — | #KiloBoyGuncellemeModal | not-read(write) |
| /Home/Index | /HastaneZiyaret/SonHastaneZiyareti | POST | __RequestVerificationToken | 200 | #HastaneZiyaret | read |
| /Home/Index | /Randevu/GetRandevularTakvimi | POST | saat, hekim, brans | — | #randevuKutu | needs-id:saat |
| /Home/Index | /Randevu/GetRandevuBilgileri | POST | saat, hekim, brans | — | #randevuKutu | needs-id:saat |
| /Home/Index | /Ziyaret/GetHastaneDegerlendirme | GET | __RequestVerificationToken | — | — | not-read(write) |
| /Home/Index | /Ziyaret/HastaneDegerlendir | GET | bilgi | — | #iYorum | not-read(write) |
| /Home/Index | /Recete/IlacHatirlatmasiEkleGoruntule | POST | — | — | #ilacHatirlatmasiEkle | not-read(write) |
| /Home/Index | /Home/IletisimBilgileriTarihGuncelleme | GET | — | — | #IletisimBilgileriGuncelleModal | not-read(write) |
| /Home/Index | /Home/GetNeyimVarLogin | GET | — | 400 | — | read |
| /Home/Index | /Bildirim/Goruldu | GET | bildirimId | — | — | not-read(unknown) |
| /Home/Index | /Home/GetASMBilgileri | GET | kurumId | — | #asmBaslik | needs-id:kurumId |
| /Home/Index | /HaciAdayi/SaglikDurumBelgesiIndir | GET | — | — | #UyariMetin | not-read(unknown) |
| /Home/Index | /OrganBagisBeyan/OrganBagisiDevamBirDahaSorma | POST | — | — | — | not-read(unknown) |
| /Home/Index | /OrganBagisBeyan/TamamlanmamisEskiOrganBagisiVarMi | POST | — | 200 | #OrganBagisinaDevamSoruModal | read |
| /Home/Index | /HizliErisim/Index | GET | key | — | — | needs-id:key |
