# CLAUDE.md — eNabizMCP

E-Nabız (T.C. Sağlık Bakanlığı Kişisel Sağlık Sistemi) verisine bir LLM üzerinden
erişmek için **yerel, salt-okunur** MCP sunucusu. **Hassas sağlık verisi (PHI)** işler;
yalnız `stdio` üzerinden çalışır.

Bu dosya *her zaman geçerli* olanı tutar. Adım-adım iş akışları skill'lerdedir
(`.claude/skills/`): yeni tool, yeni parser, endpoint keşfi, sürüm güncelleme.

## Değişmez invaryantlar (bunları asla ihlal etme)

1. **Salt-okunur.** Hiçbir tool yazma/mutasyon ucu (`/Sil`, `/Kaydet`, `/Iptal`, randevu
   al/iptal vb.) çağırmaz. Bu test edilen bir invaryant: bir yazma ucu isabet ederse
   suite kasten patlar — `tests/test_discover_scan.py:44-45`. Durum değiştiren TEK iki
   tool `enabiz_login_start` (SMS gönderir) ve `enabiz_login_verify` (oturum yazar).
2. **Sessiz yanlış-eşleme, boş sonuçtan KÖTÜDÜR.** Beklenen tablo id'si yoksa `[]` dön.
   Asla `select_one("#id") or soup.find("table")` fallback'i ekleme — bu tam olarak
   `a074eee`'de 15 parser'dan silinen sessiz-bozulma hatası (eksik id'de sayfanın ilk
   nav/layout tablosunu sağlık modeline eşliyordu). Kilitleyen test:
   `tests/test_parser_robustness.py:28-39`.
3. **PHI, LLM bağlamına girmez.** İndirme tool'ları içerik değil `{saved_path,
   byte_size, sha256, content_type}` döner (`src/enabiz_mcp/downloads.py:31-36`).
   Kimlik yalnız `.env`'den (`ENABIZ_TCKIMLIK`/`ENABIZ_SIFRE`), tool argümanı DEĞİL —
   LLM bağlamına hiç girmez. Oturum ve indirilen dosyalar `chmod 0o600`.
4. **Güvenlik kontrolleri atlatılmaz.** reCAPTCHA çözülmez, SMS OTP kaldırılmaz/kırılmaz;
   kod her zaman kullanıcının kayıtlı telefonuna gider, giriş insan-döngüdedir.
5. **PHI repoya girmez.** Testler ağsız, sentetik fixture ile çalışır. Ham portal
   yanıtları (`docs/findings/raw/`), `.env`, oturum/cookie dosyaları gitignore'dadır;
   commit'lenen bulgu `.md`'lerine gerçek değer yazılmaz.

## Komutlar

```bash
uv sync                 # bağımlılıklar
uv run enabiz-mcp       # stdio MCP sunucusu (yan etkili — canlı portala bağlanır)
uv run pytest           # test suite (ağsız; sentetik fixture, PHI'sız)
uv run ruff check       # lint    ·    uv run ruff format   # format
```

## Mimari, bir bakışta

- **`src/enabiz_mcp/parsers.py`** — saf HTML→Pydantic model dönüşümleri, yan etkisiz.
  Paylaşılan yardımcılar: `_rows()`/`_cell()` (`:164-169`), `_text()` (`:58`).
- **`src/enabiz_mcp/tools/<domain>.py`** — her biri `register(mcp)` closure'ı;
  `_common.py` ortak `auth_guarded`/`apply_limit` sağlar. Örnek: `tools/allergies.py`.
- **`src/enabiz_mcp/server.py`** — tool'ları kaydeder; 3 auth tool inline (`:47-85`),
  diğerleri `<mod>.register(mcp)` ile (`:91-116`).
- **`src/enabiz_mcp/auth.py` + `client.py` + `config.py`** — XSRF çift-token, oturum
  kalıcılığı, süreç-geneli throttle.
- **`src/enabiz_mcp/discovery.py`** — saf/ağsız keşif mantığı; **MCP tool DEĞİL**.
  Canlı tarama `scripts/discover.py`'de.

Tool/alan sayıları `README.md` ve `docs/STATUS.md`'de tutulur — CLAUDE.md'ye sabit sayı
yazma; değişiklikte oradaki sayıyı `surum-guncelle` skill'iyle güncelle.

## En sık tuzaklar (detay skill'lerde)

- Satır gezmede **`_rows(table)`** kullan, `table.select("tbody tr")` DEĞİL (tbody'siz
  tablolarda `[]` döner) — `parsers.py:168-169`.
- Hücreye `_cell(tds, i)`, metne `_text(el)` ile eriş (standart iskelet). Gerekli str
  alanı için `_cell(tds, 0) or ""` — çıplak `_cell` boş hücrede Pydantic'i patlatır.
- Çıkarılan her değer **`str`/`str | None`**; sayı/doz/tarih int/float/bool'a çevrilmez.
- `out_of_range` sunucunun `status`'undan **BAĞIMSIZ** hesaplanır ve muhafazakârdır
  (`None` dön, yanlış "aralıkta"=False değil); `_num` `"nan"/"inf"` reddeder (`:417-431`).
- **`tr_lower`/`tr_contains`** yalnız Türkçe portal metnine, karşılaştırmanın İKİ
  tarafına uygulanır; parser'ın atadığı ASCII slug'a ASLA — `tr_lower("DIGER")=="dığer"`.
  Slug filtresinde düz `.lower()` (bkz. `tools/allergies.py:46`).
- Tool decorator sırası: **`@mcp.tool` DIŞ, `@auth_guarded` İÇ** (`tools/allergies.py:22-24`).
  Tool içinde elle try/except yazma — `auth_guarded` halleder.
- Yeni tool: `server.py`'de hem `from .tools import (...)` bloğuna ekle **HEM**
  `<mod>.register(mcp)` çağır. Biri eksikse tool sessizce yüklenmez.
- Oturum-düşme kontrolü: HTTP status değil, HTML'de `name="TCKimlikNo"` (PDF'de
  `b"TCKimlikNo"`) — portal login'e 200 ile yönlendirir. `AuthRequired` fırlat.
- `has_auth_cookie()==True` oturum geçerli DEMEK DEĞİL; canlı kontrol `session_alive()`.
- Tüm HTTP `build_client` üzerinden — throttle süreç-geneli, yeni client sıfırlamaz.
- `readOnlyHint` yalnız UZAK portal mutasyonunu yansıtır; yerel dosya/ağ değil. PDF
  indiren ve `session_status` yine `True`; yalnız 2 login tool'u `False`.

## Dil ve commit

- **Identifier'lar İngilizce + ASCII.** Türkçe özel karakter (ç ğ ı ş ö ü) identifier'da
  YASAK. Türkçe yalnız (a) byte-byte API/HTML sözleşme adlarında (`TCKimlikNo`, `Sifre`,
  `baslangicTarihi`, `.hastaneAdi`, `.durumNormal`) ve (b) yorum/docstring/tool
  açıklaması/kullanıcı mesajında. İstisna: `tc_kimlik_no`, `sifre` (env ile birebir).
  Gerekçe: `docs/notes/decisions.md` D6.
- **Commit:** Conventional Commits (İngilizce type: `feat`/`fix`/`refactor`/`docs`/`chore`),
  Türkçe açıklama ve gövde, `!` = breaking. Her gövde şununla biter:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Prose dokümanlar Türkçe.
- **Commit/push yalnız kullanıcı isteyince.** Varsayılan dalda (`main`) çalışıyorsan
  önce feature dalı aç.

## Bilerek ertelenenler (körce yeniden deneme)

Organ bağışı durumu, cihaz reçete detayı, COVID tab — `docs/STATUS.md`'de gerekçeli.
