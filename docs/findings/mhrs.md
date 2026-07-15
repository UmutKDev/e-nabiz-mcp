# Bulgu: MHRS (prd.mhrs.gov.tr) — sistem, auth zinciri ve API yüzeyi

> **Gizlilik:** gerçek hasta/kimlik verisi buraya yazılmaz — yalnız alan adları,
> tipleri ve anonim/uydurma örnekler. Uç kataloğu otomatik üretilir:
> `mhrs-discovery-report.md`. Ham bundle `raw/mhrs/` (gitignored).

**Son güncelleme:** 2026-07-15 · **Kaynak build:** 2.1.405 (2 Temmuz 2026)

## Sistem sınırı

MHRS (Merkezi Hekim Randevu Sistemi) **e-Nabız'dan ayrı bir sistemdir**. E-Nabız
(KSS) sağlık *kaydını* tutar; MHRS randevu *işlemlerini* yürütür. Tek temas noktası
`vatandas/enabiz/login` SSO devridir.

E-Nabız'daki `/Home/Randevularim` tablosu (bkz. `data-models.md` — Randevular) bu
sistemin **çıktısının salt-okunur bir yansımasıdır**; randevu işlemleri orada değil,
burada olur. `Randevu Türü: MHRS` hücresi de bunu söyler.

## Mimari

React + webpack 4 SPA (Angular DEĞİL). Tek giriş `vatandas-main.js?v<sürüm>`;
webpack runtime main'in içinde inline. Lazy chunk'lar: `vatandas-<id>-chunk.js?t=<ms>`,
publicPath `/vatandas/`, chunk isim haritası **boş** → id doğrudan dosya adına girer.

**Uçlar main'de DEĞİL, chunk'lardadır.** `vatandas-main.js` içinde "slot" sıfır kez
geçer. Yalnız main'e bakan bir tarama randevu API'sini tamamen kaçırır.

**`/api/` literal'lerde geçmez.** axios `baseURL="https://prd.mhrs.gov.tr/api/"`
kurar, çağrılar relatiftir (`.get("vatandas/dil")`). Doğru arama hedefi ilk-segment
prefix'leridir: `vatandas/`, `kurum/`, `yonetim/`.

Canlı doğrulama (2026-07-15): statik varlıklarda WAF/geo-block yok, hepsi 200.
0..90 taramasında **87 chunk** bulundu (44, 88, 89, 90 yok) → 44'teki boşluk
taramayı durdurmamalı. **151 benzersiz uç**: read 71 · write 68 · unknown 12.

## Auth zinciri — e-Nabız SSO devri

Üç adım. `<...>` ile gösterilenler kişiye özeldir ve buraya YAZILMAZ.

**1. Token basımı (e-Nabız tarafı)**

```
GET https://enabiz.gov.tr/Randevu/RandevuAl?ID=<kişiye-özel-id>&vasiOnay=False
    Cookie: .EnabizSESSIONID=<...>; .AspNetCore.Antiforgery.<...>=<...>
    X-Requested-With: XMLHttpRequest
    Referer: https://enabiz.gov.tr/Home/Randevularim?randevuAl=1
→ gövde: https://prd.mhrs.gov.tr/vatandas/#/?enabizToken=<uuid>&lang=tr-TR
```

⚠️ **Adı "RandevuAl" ama randevu ALMAZ** — bir SSO token'ı basar. Buna rağmen
`enabiz_mcp.discovery._WRITE_TOKENS`'ta ADIYLA durur ve e-Nabız keşif tarayıcısı
ona dokunmaz. Denylist isim-bazlıdır; burada isim yalan söyler. Bu uç yan etkilidir
(token üretir) — `login_start`/`login_verify` ile aynı sınıfta muamele görür.

`ID` kişiye özeldir ve `/Home/Randevularim?randevuAl=1` sayfasından kazınmalıdır —
**sabit kodlanamaz (PHI)**.

**⚠️ ID sayfada bir LİNK DEĞİLDİR** — bu, canlı doğrulamanın çürüttüğü ilk iddiaydı.
Yukarıdaki `?ID=...` dizisi HTML'de **hiç geçmez**; o, tarayıcının kurduğu isteğin
şeklidir. Kaynak, "Randevu Alınacak Kişi" modalindeki `onclick` handler'ıdır:

```html
<ul class="randevuAlListe">
  <li><a onclick="linkAl('<id>','False')">          <!-- ← ID BURADA -->
```
```js
function linkAl(id, vasiOnay) {
  $.ajax({ data: { ID: id, vasiOnay: vasiOnay }, url: "/Randevu/RandevuAl", type: "GET", … })
}
```

İlk regex (`/Randevu/RandevuAl\?ID=(\d+)`) kullanıcının yakaladığı **curl'den**
türetilmişti — yani *isteğin* şeklinden, *kaynağın* şeklinden değil. Canlıda hiçbir
zaman eşleşmedi ve zincir daha ilk adımda kırıldı. Ders: yakalanan bir istek, o
isteğin nereden doğduğunu göstermez.

Tuzak: `linkAlTekrar('id','False','il',…)` ("Randevuyu Tekrarla") aynı önekle başlar,
canlı sayfada 5 kez geçer ve **farklı** bir uca gider (`/Randevu/RandevuAlTekrar`).
Regex `linkAl`'dan hemen sonra `(` istemelidir.

`vasiOnay` = vasi/kayyum onayı. Modal bir **liste**dir: kullanıcı + varsa vesayeti
altındakiler. `vasiOnay=False` olan kayıt kullanıcının KENDİSİdir; vasi akışı kapsam
dışıdır. Birden fazla vasi-olmayan kayıt varsa kod **hata verir, ilkini seçmez** —
belirsizlikte randevu yanlış kişiye yazılabilir.

**2. JWT değişimi (MHRS tarafı)**

```
POST https://prd.mhrs.gov.tr/api/vatandas/enabiz/login
     Content-Type: application/json
     {"enabizToken": "<uuid>", "islemKanali": "VATANDAS_ENABIZ_RESPONSIVE"}
→ {..., "data": {"jwt": "<...>", "uuid": "<...>", "kullaniciUuid": "<...>",
                 "refreshToken": null, "islemKanali": "VATANDAS_ENABIZ",
                 "girisTipi": {"val": 6, "valText": "e-Nabız İle Giriş"},
                 "tcKimlikNo": null, ...}}
```

**CAPTCHA YOK.** `captchaKey` yalnız parola login'inde (`vatandas/login/v2`)
görülür. Bu zincir portalın kendi resmî devir akışıdır — atlatma değildir
(invaryant #4 korunur).

**3.** Sonraki her çağrı: `Authorization: Bearer <jwt>`. SPA token'ı `token-v`
cookie'sinde tutar.

### JWT

- Ömür **20 saat** (iat→exp = 72000 s). Tek gözlemden; doğrulanmadı.
- `refreshToken: null` → yenileme yok; süre dolunca zincir baştan koşar.
- `session_alive()` (HTML'de `TCKimlikNo` arar) burada **anlamsızdır** — canlılık
  JWT `exp` (yerel) + 401/`LGN1004` (canlı) ile ölçülür.

### `islemKanali`

Endpoint değil, gövde alanı. Bundle'daki resolver viewport genişliğine bakar:
`<320` xs · `320–720` sm · `720–990` md · `>=990` lg. "lg" değilse `_RESPONSIVE`
soneki eklenir. Tam küme: `VATANDAS_WEB`, `VATANDAS_RESPONSIVE`, `VATANDAS_ENABIZ`,
`VATANDAS_ENABIZ_RESPONSIVE`, `VATANDAS_EDEVLET(_RESPONSIVE)`,
`VATANDAS_NEYIM_VAR(_RESPONSIVE)`. İstekte `..._RESPONSIVE` gönderilse de yanıtta
`VATANDAS_ENABIZ` döner → sunucu normalize eder.

## Yanıt zarfı

Tüm uçlar aynı zarfı döner:

```json
{"lang": "tr-TR", "success": true,
 "infos": [{"kodu": "GNL1009", "mesaj": "İşlem Başarılı"}],
 "warnings": [], "errors": [], "data": { ... }}
```

`success` HTTP durumundan bağımsızdır — `unwrap()` gövdeye bakar, status'a değil.

### Bilinen kodlar

| Kod | Anlam | Davranış |
|---|---|---|
| `GNL1009` | İşlem başarılı | — |
| `RNDS1010` | **Aşırı sorgu → reCAPTCHA.** ✅ bundle'da doğrulandı (17 çağrı yeri) | **Retry YOK.** Ayrıntı aşağıda. |
| `RNDS1000` | **Anti-bot kilidi (⚠️ DOĞRULANMADI).** "Hayatın olağan akışına aykırı şekilde çok fazla randevu sorgulaması yaptınız… Alo 182'yi arayınız" | **Retry YOK — sert dur.** Ayrıntı aşağıda. |
| `LGN2001` | Oturum başka cihazdan sonlandırıldı | MHRS **tek aktif oturum** tutuyor gibi → programatik login kullanıcının telefondaki oturumunu düşürebilir. Doğrulanmadı. |
| `LGN1004` | Oturum süresi doldu | Zinciri baştan koştur. |

### ⚠️ JWT `exp`'i GÜVENİLİR DEĞİL — tek oturum (canlıda ölçüldü)

Faz 1 "JWT ömrü tam 20 saat (iat→exp = 72000s), `refreshToken: null`" diyordu. `exp`
alanı doğru, ama **anlamı yanlış**: canlıda JWT yerel olarak **19.6 saat geçerli
görünürken sunucu 401 verdi**.

Sebep kullanıcı tarafından teşhis edildi: **tarayıcıdan MHRS'ye giriş yapılmıştı.**
Yani `LGN2001` tek-oturum davranışı gerçek ve **beklenenin tersi yönde de işliyor** —
endişe "bizim login kullanıcının telefonundaki oturumu düşürür" idi; gözlenen ise
**kullanıcının girişi bizim token'ı öldürüyor**. Aynı turda e-Nabız cookie oturumu da
düşmüştü.

**Bu bir kenar durum DEĞİL, normal akış:** kullanıcı MHRS'yi zaten kendi kullanıyor.
Her tarayıcı/telefon girişinde bizim token ölecek.

**Yol açtığı hata:** `mhrs_session` canlılığı yalnız yerel `exp` ile ölçüyordu, yani
ölü token cache'te "geçerli" görünüp sonsuza dek servis ediliyordu — her çağrı 401,
hiçbir şey kendiliğinden düzelmiyor. Üstelik hata ipucu "bir sonraki çağrı zinciri
yeniden koşturur" diyordu; silme olmadan bu bir **yalandı**. Düzeltildi:
`auth_guarded` `MhrsAuthRequired`'da kayıtlı JWT'yi siler (e-Nabız cookie'lerine
dokunmadan), böylece ipucu doğru olur.

**Ders:** yerel bir `exp` "sunucu bunu kabul eder" demek değildir. Token dışarıdan
her an iptal edilebiliyorsa tek geçerlilik testi sunucunun cevabıdır.

### Aşırı-sorgu kodları — kanıt durumu eşit DEĞİL

**`RNDS1010` — DOĞRULANDI.** Canlı build 2.1.405'te 17 çağrı yerinde geçiyor.
Semantiği bundle'dan ölçüldü ve sürprizli: **HTTP 428** ile gelir, **yanıtta sonuçlar
VARDIR** (`dataList: e.response.data.data`), ve istemci sunucunun mesajını modal'da
gösterip **`randevuAraReCAPTCHAVisible: true`** yapar. Yani anlamı: *"çok arama
yaptın; sonuçların burada ama bundan sonra reCAPTCHA çöz"* — **yumuşak** eşik, sert
kilit değil.

**Bizim için yine de terminaldir:** reCAPTCHA çözmüyoruz (invaryant #4), dolayısıyla
tekrar denemenin faydası yok, yalnız eşiği derinleştirir.

**`RNDS1000` — DOĞRULANMADI.** Bundle'da **sıfır kez** geçiyor. Kamuya açık MHRS
mesajı gerçektir, ama kodunun bu olduğu bu repoda hiçbir yerde kanıtlanmadı; iddia
daha eski bir oturumdan taşındı ve sorgulanmadan tekrarlandı — kod, config, testler
ve bu doküman baştan sona onun üzerine kuruldu.

Listede **kalıyor**, çünkü yanılmanın maliyeti asimetrik: kod yoksa o dal hiç
tetiklenmez (bedava), varsa kullanıcıyı online randevudan çıkaran kilidi yakalar.

**Yaşanan hata:** koruma bir tur YALNIZ `RNDS1000`'e bağlıydı — yani bundle'da
olmayan bir koda. `RNDS1010` jenerik `MhrsError`'a düşüyor, "TEKRAR DENEMEYİN" ipucu
modele hiç ulaşmıyor ve model retry edebiliyordu: korumanın tam olarak engellemek
için yazıldığı senaryo. Ölçüldü ve düzeltildi (`client.RATE_LIMIT_CODES`).

**Ders:** bir hata kodu etrafında savunma kurarken önce o kodun VAR olduğunu kanıtla.
Doğru mesaj + uydurma kod = çalışmayan koruma.

`yonetim/genel/mesaj/by-kodu/<KOD>` ucu mesaj metinlerini döndürür; bundle'da
referans verilenler: `GNL2016`, `GNL2030`, `RND4105`, `RND6041`, `RND6042`,
`RNDG1000`, `RNDG1001`, `RNDI1003`, `RNDNEY1000`, `VTP1002`.

## Keşfin iki kör noktası (ölçüldü, düzeltildi)

İlk tarama **151 uç** buldu ve eksiksiz GÖRÜNÜYORDU. İki ayrı hata tüm bir uç
ailesini sessizce düşürüyordu; ikisi de yalnız bundle elle taranınca ortaya çıktı.
Rapor şimdi **161 uç**.

**1. `kurum-rss/` prefix'i düştü — Faz 2'nin TÜM çekirdeği.**
`API_PREFIXES = ("vatandas/", "kurum/", "yonetim/")` iken `kurum-rss/...` hiçbir
alternatifle eşleşmedi. `kurum-rss` ile `kurum` KARDEŞ prefix'lerdir. Kaçan iki uç
slot arama ve slot listelemedir — yani randevu almanın önündeki her şey.

**2. Baştan slash'lı yollar düştü — 7 uç.**
Çıkarıcı literalin prefix'le BAŞLAMASINI şart koşuyordu; bundle ise iki biçimi de
kullanıyor (`.get("vatandas/dil")` ama `.put("/vatandas/dil/dil-bilgileri/")`).
axios ikisini de aynı `baseURL`'e çözer → aynı uçturlar. Kaçanlardan biri
`PUT vatandas/hesap-bilgileri/parola-degistir` — haritada görünmeyen bir **parola
değiştirme** ucu.

**Ders — allowlist sessizce daraltır.** Güvenlidir (yanlış pozitif üretmez) ama
düşürdüğünü hiçbir yere yazmaz; rapor tam görünür. `discover_mhrs.py` artık kendi
kör noktasına bakıyor: `audit_unknown_prefixes` allowlist dışı her prefix'i sayar,
operatöre bağırır ve rapora `cikarilmayan_prefix` olarak yazar. Sessiz daraltma →
gürültülü daraltma. (Denetçi bir tur çıkarıcıyla AYNI kör noktayı paylaşıyordu —
baştaki slash'ı o da reddediyordu. Kör noktayı arayan araç aynı kör noktaya
sahipse hiçbir şey bulmaz; `tests/test_mhrs_discovery.py::test_no_unknown_api_prefixes`
artık iki deseni birbirine bağlı tutuyor.)

## Uç kataloğu

Tam liste: **`mhrs-discovery-report.md`** (otomatik üretilir). Öne çıkanlar:

### Okuma — randevu arama
| Uç | Not |
|---|---|
| `POST kurum-rss/randevu/slot-sorgulama/arama` | **kurum/klinik arama — gövdeli POST, ama OKUMA** |
| `POST kurum-rss/randevu/slot-sorgulama/slot` | **slot listesi — Faz 2'nin kalbi; gövdeli POST, OKUMA** |
| `GET yonetim/genel/il/selectinput-tree` | il listesi (ağaç: `[].text/value/children[]`) |
| `GET yonetim/genel/ilce/selectinput/{ilId}` | ilçe (düz: `[].value/text`) |
| `GET kurum/kurum/kurum-klinik/klinik/select-input` | klinik |
| `GET kurum/kurum/kurum-klinik/il/{il}/ilce/{ilce}/kurum/{kurum}/klinik/{klinik}/ana-kurum/select-input` | kurum-klinik zinciri |
| `GET kurum/kurum/muayene-yeri/ana-kurum/{p1}/kurum/{p2}/klinik/{p3}/select-input` | `-1` = "hepsi" sentinel'i |
| `GET kurum/randevu/slot-sorgulama/randevu-bilgileri?fkSlotId={id}` | slot detayı — **⚠️ slot kilidi kuruyor olabilir, aşağıya bak** |
| `GET kurum/randevu/slot-sorgulama/en-gec-gun/by-aksiyon?aksiyonId={id}` | en geç gün |
| `GET kurum/randevu/yaklasan-randevularim` · `randevu-gecmisi` · `kurum/randevu-arsiv/randevu-arsiv` | randevu listeleri |
| `GET yonetim/genel/parametre/degeri/SLOT_LISTELEME_MAX_GUN_WEB` | slot listeleme ufku (yalnız istemci görüntüsü; isteğe GÖNDERİLMEZ) |

### POST ile OKUYAN uçlar — metot da sinyal değil

`slot-sorgulama/arama` ve `slot-sorgulama/slot` **POST'tur ama okumadır**: filtre
gövdesi 13-16 alanlı (dizi alanı `randevuZamaniList` dahil), query string'e sığmıyor.
Klasik "POST-as-search".

Bu, ad-bazlı sınıflamanın simetrik yüzü: MHRS GET ile yazıyor **ve** POST ile
okuyor. Metot kapısı tek başına ikisinde de yanılır. Sınıflandırıcı bunu dar,
elle incelenmiş bir allowlist ile karşılıyor (`discovery._READ_POSTS`); varsayılan
**"POST = yazma" olarak KALIR** ve yazma sözcüğü kapısı allowlist'ten ÖNCE koşar,
yani istisna bir yazma ucunu asla kurtaramaz.

Kanıt (bundle, `vatandas-45-chunk.js`): dönen liste yalnız render ediliyor
(`.then(e => e.data.success && t(e.data.data))`), hiçbir state commit edilmiyor;
aynı gövde filtre değiştikçe defalarca POST'lanıyor (idempotent); gerçek mutasyonlar
ayrı ve adı açık yollarda (`randevu-ekle`, `randevu-iptal-et-yeni-al`).

### ⚠️ `randevu-bilgileri` masum değil — slot kilidi

`GET kurum/randevu/slot-sorgulama/randevu-bilgileri?fkSlotId={id}` adı ve metodu
"detay okuma" diyor, ama istemci onay modalını **iptal ettiğinde**
`DELETE kurum/randevu/slot-kilitleme` çağırıyor (`vatandas-10-chunk.js`) — yani bu
çağrı sunucuda bir kilit BIRAKIYOR, demek ki bir yerde kilit KURULMUŞ. En olası
kuran, slot detayını isteyen çağrının kendisi.

**Doğrulanmadı** (canlı gözlem gerekir) ama Faz 3'ün tasarımını bağlar: plan
`book_prepare`'i "hiçbir şey yazmaz, `readOnlyHint: True`" diye tarif ediyordu —
kilit gerçekse bu YANLIŞ ve `book_prepare` iptal edildiğinde kilidi bırakmak
zorunda. Faz 3'te canlı doğrulanacak.

### Faz 2 sözleşmeleri — CANLI DOĞRULANDI (build 2.1.405, 2026-07-15)

Aşağıdakiler önce bundle'dan çıkarıldı, sonra canlı hesaba karşı koşuldu. Canlı
tur iki şeyi düzeltti:

**1. Hekim adı SESSİZCE düşüyordu.** `yaklasan-randevularim` ve `randevu-gecmisi`
hekimi PARÇALI gönderiyor (`mhrsHekimAd` + `mhrsHekimSoyad`); tek alanlı
`hekimAdSoyad` yalnız `randevu-arsiv`'e ait. Parser yanlış alanı arıyordu → hekim
adı hiç gelmiyordu. Kayıt boş değil, **eksikti** — "boş sonuç > sessiz yanlış-eşleme"
invaryantı bu sınıfı yakalamaz; yakalayan tek şey canlı alan adı karşılaştırmasıydı.

**2. Sunucu beklenenden ÇOK daha fazla alan döndürüyor** — randevu DTO'sunda 43 alan.
Faz 3 için kritik olanı: **`iptalEdilebilirMi`** ve `iptalGecerlilikZamani` — yani
iptal edilebilirliği kendi kuralımızla hesaplamamıza gerek yok, sunucu söylüyor.
Ayrıca `randevuTuruAdi`, `randevuNotu`, `gizliRandevu`, `goruntuluRandevuLinki`,
`ayniHekimdenRandevuAl`, `randevuGeriAlinabilir` var (henüz kullanılmıyor).

Canlı ölçümler: il **85** kayıt (81 değil — MHRS İstanbul'u ANADOLU/AVRUPA diye
`children` ile bölüyor), klinik 80. `randevuBaslangicZamaniStr` beklenen
`{tarih, gun, saat, zaman}`'ın yanında `date`, `gunAyGunIsmi`, `tarihAy` da taşıyor.

Slot uçlarının (`kurum-rss/...`) gövde şekli HÂLÂ canlı doğrulanmadı — Faz 2b.

**`POST kurum-rss/randevu/slot-sorgulama/slot`** — gövde:
`aksiyonId, mhrsKurumId, mhrsKlinikId, mhrsHekimId, mhrsIlId, mhrsIlceId,
muayeneYeriId, cinsiyet, tumRandevular, ekRandevu, randevuZamaniList,
uzaktanDegerlendirmeGoster`. Yanıt (`data[]`):
```
data[].gun
data[].hekimSlotList[].hekim.{ad, soyad, mhrsHekimId}
data[].hekimSlotList[].klinik.lcetvelTipi          # yazım hatası DEĞİL, baştaki 'l' gerçek
data[].hekimSlotList[].muayeneYeriSlotList[].muayeneYeri.adi
data[].hekimSlotList[].muayeneYeriSlotList[].saatSlotList[].{saatStr, bos, ek,
                                                             uzaktanDegerlendirmeVarmi}
data[].hekimSlotList[].muayeneYeriSlotList[].saatSlotListEk[]   # "ek" (fazla mesai) slotları
```

**`GET kurum/randevu/yaklasan-randevularim`** ve **`randevu-gecmisi`** — parametresiz
(gecmisi opsiyonel `baslangicTarihi` alır). İkisi de ÜÇ liste döner:
`aktifRandevuDtoList[]`, `gecmisRandevuDtoList[]`, `gizliRandevuGecmisiDtoList[]`.
Randevu nesnesi: `hastaRandevuNumarasi` (= **hrn**, iptalin anahtarı),
`randevuBaslangicZamaniStr.{tarih, gun, saat, zaman}`, `randevuBitisZamaniStr.saat`,
`kurumAdi`, `ek`, `shmMi`, `randevuKayitDurumu.{val, valText}`.

**Tuzaklar (bundle'da ölçüldü):**
- **`cinsiyet:"F"` SABİT KODLU** (`vatandas-18-chunk.js`). Formda cinsiyet seçimi yok.
  Muhtemelen "Farketmez" ama bundle bunu doğrulamıyor — sadece literalin varlığı kesin.
- **`randevuTuruId` okunuyor ama hiçbir gövde kurucusu SET ETMİYOR** → pratikte
  `undefined` gidiyor. İsteğe eklenmemeli.
- **`-1` sentinel'i sistematik** ("farketmez"). Ama kurucudaki `parseFloat(x) || -1`
  zinciri **0'ı da -1'e çevirir** (0 falsy) — MHRS bunu bir yerde elle telafi ediyor
  (`mhrsHekimId: 0 !== e.mhrsHekimId ? e.mhrsHekimId : -1`).
- **İsim tutarsızlığı:** ana form `muayeneYeriId`, kısayol akışları `mhrsMuayeneYeriId`.
  Hangisinin kanonik olduğu bundle'dan çıkarılamadı.
- **`slot` ile `arama` FARKLI şekil döner:** `arama` bir NESNE
  (`{semtAramasi, hastane[], semt[], alternatif[], ekVar}`), `slot` bir DİZİ.

### ⚠️ Yazma — GET ile yazan uçlar

**HTTP metodu güvenlik sinyali DEĞİLDİR.** MHRS'de 12 uç GET ile yazar:

| Uç | Etki |
|---|---|
| `GET kurum/randevu/ayni-hekimden-randevu-al/{id}` | **GET ile RANDEVU ALIR** |
| `GET kurum/randevu/iptal-et/{hrn}` · `iptal-et-hrn-uuid/{p1}/{p2}` | randevu iptal eder |
| `GET kurum/randevu/geri-al/{id}` | işlemi geri alır |
| `GET kurum/randevu/degisikligi-onayla/{id}` · `-reddet/{id}` · `degisikligi-istisna-*` | değişiklik onay/ret |
| `GET kurum/randevu/cakisma-onay/{id}` | çakışma onayı |
| `GET kurum/randevu-ozellik/gizle/{id}` · `gizlilik-kaldir/{id}` | randevu gizler |
| `GET kurum/randevu-talep/bilgilendir/{id}` | bildirim gönderir |

Bu yüzden `mhrs/discovery.py` sınıflaması **ad-bazlıdır** ve **tüm yolu** tarar
(fiil ortada, id sonda: `kurum/randevu/iptal-et/{hrn}`). E-Nabız'ın son-segment
yaklaşımı burada `{hrn}` döndürür ve fiili kaçırır.

Ayrıca e-Nabız'ın denylist'i kebab-case'de körelir — **ampirik**:
`_WRITE_TOKENS.search("randevu-al") is None` (bitişik `RandevuAl` arıyor). MHRS
kendi tire-duyarlı denylist'ini kullanır; fork değil.

### Yazma — POST/PUT/DELETE
`POST kurum/randevu/randevu-ekle` (randevu alma) · `POST kurum/randevu/randevu-iptal-et-yeni-al` ·
`DELETE kurum/randevu/slot-kilitleme` · `POST/PUT/DELETE kurum/randevu-notlari` ·
`POST kurum/randevu-talep` · `PUT vatandas/favori/ekle` · `POST vatandas/uyelik` …
Tam liste raporda.

## Kısıtlar ve riskler

- **RNDS1000 (anti-bot):** slot arama **poll döngüsü yapmamalı**. Eşik bilinmiyor;
  `ENABIZ_MHRS_MIN_INTERVAL` (varsayılan 2.0 s) bir tahmindir, ölçüm değil.
- **Rate limit IP-tabanlı** (hesap değil) → CGNAT arkasındaki masum kullanıcılar da
  etkilenir. Blok tipik 30 dk–1 saat.
- **No-show cezası GERÇEK:** randevuya gitmeyen/iptal etmeyen **aynı branştan 15 gün**
  randevu alamaz (T.C. Sağlık Bakanlığı duyurusu, saglik.gov.tr TR,94138). **Para
  cezası iddiası YALAN** (AA Teyit "Yanlış"; tüm MHRS işlemleri ücretsiz — para cezası
  bildirimi gönderen siteler dolandırıcılıktır). Sonuç: yanlış otomatik randevu
  kullanıcıya gerçek bir branş yasağı yazdırır → randevu alma **iki adımlı onaylıdır**.
- **`robots.txt` `Disallow: /api/`** (`Allow:` yalnız `/` ve `/vatandas/`). Statik
  bundle keşfi açıkça izinlidir; `/api/` erişimi değildir. Kullanıcı kendi hesabına
  kendi adına eriştiği için devam kararı verildi — kayda geçer.
- **Kırılganlık:** chunk id'leri ve cache-buster (`?t=`, `?v`) her deploy'da değişir.
  Tarayıcı şablonu her koşuda yeniden okur, sabit kodlamaz.
- **Uçlar doğrulanmadı:** 151 uç *istemci kodunda çağrıldığı* için var sayıldı;
  sunucuda o imzayla yaşadıkları kanıtlanmadı (ölü kod olabilir).

## Prior art

Resmî API dokümanı yok. Swagger UI var ama kimlik-korumalı
(`prd.mhrs.gov.tr/docs/swagger/login`).

- `ShaZzam0/paracci-mhrs-randevu-botu` — Python, salt-okunur slot checker; README'de
  örnek yanıt gövdeleri.
- `cagoshian/mhrs-otorandevu` — Node, tam `randevu-ekle` akışı.

İkisi de parola login'i (`kullaniciAdi`/`parola`/`islemKanali: VATANDAS_WEB`/
`girisTipi: PAROLA`) kullanır — bizim SSO zincirimizden farklı. Refresh yapmazlar;
`LGN1004` görünce sıfırdan login olurlar.
