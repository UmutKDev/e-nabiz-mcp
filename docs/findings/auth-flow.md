# Bulgu: E-Nabız kimlik doğrulama akışı

> Kaynak: `enabiz.gov.tr/Account/Login` GET yanıtının analizi + kullanıcının
> sağladığı `GetSmsOnayKontrol` curl'ü. Gerçek token/cookie/kimlik değerleri
> **bu dosyaya yazılmaz** (yalnızca yapı/desen).

## Özet

Portal **ASP.NET Core** tabanlı. Giriş üç katmanla korunuyor:

1. **Antiforgery (XSRF) çift-token** — otomatikleştirilebilir ✅
2. **Google reCAPTCHA** — bot-engelleme; atlatılmaz ⛔ (insan-döngüde)
3. **SMS OTP (2FA)** — atlatılmaz ⛔ (kod kullanıcıdan alınır)

---

## 1) XSRF / Antiforgery mekanizması (DOĞRULANDI)

Standart ASP.NET Core "cookie + gizli alan çift-gönderim" deseni.

### `GET /Account/Login` yanıtı şunları verir:
- **Cookie:** `Set-Cookie: .AspNetCore.Antiforgery.<rasgele>=<değer>; path=/; samesite=strict; httponly`
- **Cookie:** `Set-Cookie: SAGLIK<hex>=<değer>; Domain=.enabiz.gov.tr; Secure; HttpOnly`
  → WAF/yük dengeleyici oturum cookie'si (muhtemelen BIG-IP benzeri).
- **Gizli alan** (HTML gövdesinde, birden çok formda):
  ```html
  <input name="__RequestVerificationToken" type="hidden" value="CfDJ8...">
  ```
- **Inline JS** (jQuery `ajaxSetup`): her XHR'ye header ekliyor:
  ```js
  beforeSend: function (xhr) {
      xhr.setRequestHeader("XSRF-TOKEN",
          $('input[name="__RequestVerificationToken"]').val());
  }
  ```

### POST'u yeniden üretme (reçete)
1. `GET /Account/Login` yap → cookie jar'da `.AspNetCore.Antiforgery.*` + `SAGLIK*`
   otomatik saklanır; HTML'den `__RequestVerificationToken` **value**'sunu kazı.
2. POST'ta:
   - Cookie'leri gönder (jar otomatik).
   - Header ekle: `XSRF-TOKEN: <kazınan token>` (HTTP header adı büyük/küçük duyarsız;
     orijinal curl'de `xsrf-token` olarak da geçiyor).
   - Header ekle: `X-Requested-With: XMLHttpRequest`.
   - Gövde: `application/x-www-form-urlencoded`.

> Kullanıcının `GetSmsOnayKontrol` curl'ü bunu birebir doğruluyor: `xsrf-token`
> header + `.AspNetCore.Antiforgery.*` cookie var, **gövdede token yok**.

### Uygulama notu (`src/enabiz_mcp/auth.py`)
- `get_antiforgery(client) -> str`: login sayfasını GET eder, `httpx` cookie jar'ı
  doldurur, `BeautifulSoup` ile `input[name=__RequestVerificationToken]` value döner.
- Token değeri isteğe özeldir; her yeni oturumda tazelenir.

---

## 2) reCAPTCHA

- Login sayfası `https://www.google.com/recaptcha/api.js?hl=tr` yüklüyor.
- **Gözlem:** `GetSmsOnayKontrol` POST'unda reCAPTCHA token'ı YOK → bu adım
  muhtemelen captcha gerektirmiyor. Nihai `Login`/`SMSOnayi` adımı gerektirebilir.
- **İlke:** reCAPTCHA **çözülmez/atlatılmaz**. Bir adım captcha'ya takılırsa o adım
  için **oturum-içe-aktarma yedeği** kullanılır (aşağıda).

---

## 3) SMS OTP (2FA) — DOĞRULANDI (canlı, 2026-07-12)

İki-aşamalı giriş akışı (login sayfası JS'i + canlı istekle doğrulandı):

| Adım | Endpoint | Method | Params | Yanıt kodları |
|---|---|---|---|---|
| 1 | `/Account/GetSmsOnayKontrol` | POST | `TCKimlikNo`, `Sifre` | `22`=kimlik OK→SMS onayına geç · `87`=işlem hatası |
| 2 | `/Account/GetSmsOnayGirisYap` | POST | `tc`, `onayKodu` | `1`=giriş başarılı (`location.href="/"`) · `2`=kod eşleşmiyor · diğer→`/Account` |

- **Adım 1** canlı test edildi → `200 application/json`, gövde `22`. Kimlik bilgileri
  doğru; SMS sunucu tarafından bu adımda gönderiliyor (ayrı bir "gönder" çağrısı yok).
- **Auth cookie** adım 2'nin `1` yanıtıyla set ediliyor (JS ardından `/`'a yönlendiriyor).

### ⚠️ Ayrı akış — bu login DEĞİL
`SmsGonderimKontrol` ({ceptelefonu}) ve `SMSOnayi` ({tc, cep}) → telefon-doğrulama/
şifre-SMS akışı (`#telefonOnayModal`, `#sifreonaykoduid`). Login 2FA'sı ile karıştırma.

### MCP tasarımı (iki-adımlı)
- `enabiz_login_start()` → adım 1; "22 → SMS gönderildi" döner.
- `enabiz_login_verify(otp_code)` → adım 2 (`GetSmsOnayGirisYap`); oturumu kaydeder.
- Antiforgery cookie+token adımlar arası `pending.json` (repo-dışı, chmod 600) ile korunur.

---

## Oturum kalıcılığı
- Kimlikli cookie'ler yerel dosyaya (`~/.config/enabiz-mcp/session.json`, `chmod 600`)
  yazılır, süresi dolana dek yeniden kullanılır.
- **Gözlem (2026-07-13):** `.EnabizSESSIONID` **kısa ömürlü** (~dakikalar; ~30-60 dk
  içinde düştü). Süre dolunca kimlikli sayfa login'e redirect eder → `scrape_token`
  bunu `AuthRequired` ile yakalıyor (doğrulandı). **Faz 4:** otomatik yeniden-auth istemi.
- Süre dolunca 401/redirect algılanır → yeniden `login_start`/`login_verify`.
- Not: antiforgery cookie kısa ömürlü olabilir (portal doküman notu ~8 dk); auth
  cookie'si ayrı ve daha uzun ömürlüdür — ikisi karıştırılmamalı.

## Yedek yol — oturum içe aktarma
Betikle giriş herhangi bir adımda reCAPTCHA/anti-otomasyona takılırsa: kullanıcı
tarayıcıda normal giriş yapar, kimlikli cookie(ler) MCP'ye aktarılır (env/dosya),
MCP yalnızca salt-okunur veri çağrılarında bu oturumu + XSRF'i kullanır.

## Açık sorular (Faz 1)
- [ ] `GetSmsOnayKontrol` yanıt şekli nedir? (JSON? SMS gerekli/gereksiz ayrımı?)
- [ ] SMS'i hangi endpoint tetikliyor, hangi parametrelerle?
- [ ] `SMSOnayi` başarılı yanıtı ve set edilen auth cookie adı?
- [ ] Nihai adımlarda reCAPTCHA zorunlu mu?
