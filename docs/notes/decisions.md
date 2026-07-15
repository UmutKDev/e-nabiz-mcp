# Kararlar (ADR)

Kısa, tarih damgalı mimari/yön kararları.

## 2026-07-12

### D1 — Stack: Python + FastMCP
`uv` + **FastMCP** (`fastmcp` v3) + `httpx` (cookie jar) + `BeautifulSoup`.
Gerekçe: kaz​ıma/tersine-mühendislik için doğal; kullanıcı ortamında Python + uv
hazır; hızlı prototipleme. (Alternatif: TypeScript resmi SDK — reddedildi.)

### D2 — Auth stratejisi: betikle giriş + OTP istemi
MCP, XSRF'i otomatik yönetir ve credential POST'u kendisi yapar; SMS OTP kodunu
kullanıcıdan ister (iki-adımlı `login_start`/`login_verify`). reCAPTCHA/SMS
**atlatılmaz**. Herhangi bir adım anti-otomasyona takılırsa **oturum-içe-aktarma**
yedeğine geçilir.
Gerekçe: en fazla otomasyon + güvenlik kontrollerine saygı.

### D3 — Transport: yerel stdio
PHI hassasiyeti nedeniyle uzak transport yok. Bkz. `docs/privacy.md`.

### D4 — İlk veri önceliği: Tahliller/Tetkikler
Keşif ve ilk MCP tool'ları laboratuvar sonuçlarına odaklanır; diğer alanlar
(reçete, randevu, rapor/görüntü, aşı, ölçüm) aynı desenle eklenir.

### D5 — Python sürümü 3.14 → 3.13
Wheel uyumluluğu (pydantic-core vb.) için proje 3.13'e sabitlendi; `requires-python
>= 3.11`.

### D6 — İsimlendirme konvansiyonu: İngilizce identifier + Türkçe sözleşme/yorum
Tüm identifier'lar (fonksiyon, sınıf, değişken, sabit, modül, tool parametresi)
**İngilizce ve ASCII**. Türkçe **yalnızca** şurada kalır:
- **API/HTML sözleşme adları** (birebir eşleşmeli): istek anahtarları (`"TCKimlikNo"`,
  `"Sifre"`, `"baslangicTarihi"`, `"onayKodu"`, `"IslemTipi"`) ve CSS seçicileri
  (`.hastaneAdi`, `.durumNormal`, `.rowContainer`).
- **Yorumlar, docstring'ler, MCP tool açıklamaları** ve kullanıcıya dönen mesajlar.
- **İstisna — özel ad:** İngilizce net karşılığı olmayan kimlik alanları
  `tc_kimlik_no`, `sifre` (env `ENABIZ_TCKIMLIK`/`ENABIZ_SIFRE` ile birebir).

**Yasak:** identifier'da Türkçe özel karakter (ç,ğ,ı,ş,ö,ü) — `ı`/`i` küçük/büyük
harf tuzağı ve tooling sürtünmesi.

Gerekçe: dilin keyword'leri İngilizce; sektör konvansiyonu; `.lower()`/`.upper()`
Türkçe I sorunları; grep/autocomplete/linter uyumu.
