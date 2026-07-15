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
**sabit kodlanamaz (PHI)**. `vasiOnay` = vasi/kayyum onayı; vasi akışı kapsam dışı.

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
| `RNDS1000` | **Anti-bot kilidi.** "Hayatın olağan akışına aykırı şekilde çok fazla randevu sorgulaması yaptınız… Alo 182'yi arayınız" | **Retry YOK — sert dur.** Kullanıcıyı online randevudan tamamen çıkarır; zarar hız kaybı değil, **erişim kaybı**. |
| `LGN2001` | Oturum başka cihazdan sonlandırıldı | MHRS **tek aktif oturum** tutuyor gibi → programatik login kullanıcının telefondaki oturumunu düşürebilir. Doğrulanmadı. |
| `LGN1004` | Oturum süresi doldu | Zinciri baştan koştur. |

`yonetim/genel/mesaj/by-kodu/<KOD>` ucu mesaj metinlerini döndürür; bundle'da
referans verilenler: `GNL2016`, `GNL2030`, `RND4105`, `RND6041`, `RND6042`,
`RNDG1000`, `RNDG1001`, `RNDI1003`, `RNDNEY1000`, `VTP1002`.

## Uç kataloğu

Tam liste: **`mhrs-discovery-report.md`** (otomatik üretilir). Öne çıkanlar:

### Okuma — randevu arama
| Uç | Not |
|---|---|
| `GET yonetim/genel/il/selectinput-tree` | il listesi |
| `GET yonetim/genel/ilce/selectinput/{ilId}` | ilçe |
| `GET kurum/kurum/kurum-klinik/klinik/select-input` | klinik |
| `GET kurum/kurum/kurum-klinik/il/{il}/ilce/{ilce}/kurum/{kurum}/klinik/{klinik}/ana-kurum/select-input` | kurum-klinik zinciri |
| `GET kurum/kurum/muayene-yeri/ana-kurum/{p1}/kurum/{p2}/klinik/{p3}/select-input` | `-1` = "hepsi" sentinel'i |
| `GET kurum/randevu/slot-sorgulama/randevu-bilgileri?fkSlotId={id}` | slot detayı |
| `GET kurum/randevu/slot-sorgulama/en-gec-gun/by-aksiyon?aksiyonId={id}` | en geç gün |
| `GET kurum/randevu/yaklasan-randevularim` · `randevu-gecmisi` · `kurum/randevu-arsiv/randevu-arsiv` | randevu listeleri |
| `GET yonetim/genel/parametre/degeri/SLOT_LISTELEME_MAX_GUN_WEB` | slot listeleme ufku |

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
