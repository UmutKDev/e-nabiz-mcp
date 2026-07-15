# Tasarım: `.claude/` kurulumu (CLAUDE.md + skills + settings + subagent + komutlar)

**Tarih:** 2026-07-14
**Durum:** onaylandı (kullanıcı)
**Kapsam:** eNabizMCP reposu için Claude Code çalışma-zamanı yapılandırması.

## Amaç

Bir ajanın (Claude Code) bu repoda güvenli ve konvansiyona uygun çalışabilmesi için
gereken bağlamı kurmak: her zaman geçerli invaryantları/komutları taşıyan ince bir
`CLAUDE.md`, tekrar eden iş akışları için skill'ler, sürtünmeyi azaltan izin
allowlist'i, ve diff'i denetleyen bir güvenlik ajanı.

Bütün içerik Türkçe (repo tutarlılığı). Bütün teknik iddialar kodda `file:line`
veya commit hash'i ile çapalı — bu spec'in temelindeki harita altı paralel okuyucu
+ bir doğrulama pası ile üretildi ve her `file:line` doğrulandı.

## Yön kararı

**Yaklaşım A — ince CLAUDE.md + kalın skill'ler.** CLAUDE.md yalnız *her turda geçerli*
olanı taşır (invaryant, komut, en sık tuzak). Adım-adım iş akışları skill'lere iner ve
yalnız o iş yapılırken yüklenir. Gerekçe: tekrar minimum, bağlam şişmesi yok, kural
tek yerde yaşar (çürüme riski düşük). (Reddedilenler: B = tek kalın dosya, skill yok;
C = her şeyi iki yerde tekrarla.)

## Dosya yapısı

```
CLAUDE.md
.claude/
  settings.json
  skills/
    yeni-tool-ekle/SKILL.md
    yeni-parser-ekle/SKILL.md
    endpoint-kesfet/SKILL.md
    surum-guncelle/SKILL.md
  agents/
    guvenlik-denetcisi.md
  commands/
    yeni-tool.md
    yeni-parser.md
    kesfet.md
    surum.md
```

## 1. `CLAUDE.md` (kök, ince, ~90-110 satır)

Bölümler:

1. **Proje bir cümle** — yerel, salt-okunur E-Nabız MCP; PHI işler; `stdio`.
2. **Değişmez invaryantlar** (en üstte):
   - **Salt-okunur.** Hiçbir tool yazma/mutasyon ucu (`/Sil`, `/Kaydet`, `/Iptal`,
     randevu al/iptal) çağırmaz. Test tripwire'ı: `tests/test_discover_scan.py:44-45`
     bir yazma ucu isabet ederse `AssertionError("Yazma ucu ... salt-okunur ihlali!")`
     atar. Yalnız `enabiz_login_start` (SMS gönderir) ve `enabiz_login_verify`
     (oturum yazar) durum değiştirir.
   - **Sessiz yanlış-eşleme > boş sonuç.** Beklenen tablo id'si yoksa `[]` dön; asla
     `select_one("#id") or soup.find("table")` fallback'i ekleme (bu tam olarak
     `a074eee`'de silinen sessiz-bozulma hatası).
   - **PHI LLM'e girmez.** İndirme tool'ları içerik değil `{saved_path, byte_size,
     sha256, content_type}` döner (`downloads.py:31-36`). Kimlik yalnız `.env`
     (`ENABIZ_TCKIMLIK`/`ENABIZ_SIFRE`), tool argümanı değil. Oturum/indirme dosyaları
     `chmod 0o600`.
   - **Güvenlik kontrolleri atlatılmaz.** reCAPTCHA çözülmez, SMS OTP kaldırılmaz;
     giriş insan-döngüde.
3. **Komutlar** — `uv sync`; `uv run enabiz-mcp` (stdio sunucu); `uv run pytest`
   (ağsız, sentetik fixture); `uv run ruff check` / `ruff format`.
4. **Mimari bir bakışta** — `parsers.py` saf HTML→Pydantic model (yan etkisiz);
   `tools/<domain>.py` her biri `register(mcp)` closure'ı; `server.py` import + register
   + 3 inline auth tool; `auth.py`/`client.py` XSRF çift-token + oturum + throttle;
   `discovery.py` saf/ağsız, MCP tool DEĞİL, canlı tarama `scripts/discover.py`'de.
5. **En sık tuzaklar** (kısa; detay skill'lerde):
   - Satır gezmede `_rows(table)` kullan, `table.select("tbody tr")` DEĞİL (tbody'siz
     tablolarda `[]` döner) — `parsers.py:168-169`.
   - Hücreye `_cell(tds, i)`, metne `_text(el)` ile eriş (standart iskelet).
   - Çıkarılan her değer `str`/`str | None`; sayı/doz/tarih int/float'a çevrilmez.
   - `out_of_range` sunucunun `status`'undan BAĞIMSIZ hesaplanır ve muhafazakârdır
     (`None` dön, yanlış "aralıkta" değil); `_num` `"nan"/"inf"` reddeder.
   - `tr_lower`/`tr_contains` yalnız Türkçe portal metnine, KARŞILAŞTIRMANIN İKİ
     TARAFINA; parser'ın atadığı ASCII slug'a asla (`tr_lower("DIGER")=="dığer"`).
   - Tool decorator sırası: `@mcp.tool` DIŞ, `@auth_guarded` İÇ.
   - Yeni tool: `server.py`'de hem import bloğuna ekle HEM `register()` çağır; biri
     eksikse tool sessizce yüklenmez.
   - `has_auth_cookie()==True` oturum geçerli DEMEK DEĞİL; canlı kontrol `session_alive()`.
   - Bütün HTTP `build_client` üzerinden (throttle process-global, yeni client sıfırlamaz).
6. **Dil & commit** — D6: identifier'lar İngilizce+ASCII, Türkçe özel karakter (ç ğ ı ş
   ö ü) identifier'da YASAK; Türkçe yalnız (a) byte-byte API/HTML sözleşme adları
   (`TCKimlikNo`, `.hastaneAdi`) ve (b) yorum/docstring/mesaj. İstisna: `tc_kimlik_no`,
   `sifre`. Commit: Conventional Commits (İngilizce type) + Türkçe açıklama/gövde,
   `!`=breaking, gövde sonunda `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
7. **Bilerek ertelenenler** (körce yeniden deneme) — organ bağışı durumu, cihaz reçete
   detayı, COVID tab. Bkz. `docs/STATUS.md`.

Kural: her madde `file:line` veya commit ile çapalı.

## 2. Skill'ler (`.claude/skills/<ad>/SKILL.md`)

Her dosya: YAML frontmatter (`name`, `description` — ne zaman tetikleneceğini net
tarif eder) + numaralı checklist. Ajan checklist'in her maddesini bir task'a çevirir.

### 2.1 `yeni-tool-ekle` (uçtan uca, diğerlerini kapsar)
1. Endpoint'i doğrula: `docs/findings/discovery-report.md` / `endpoints.md`; yoksa
   `endpoint-kesfet` skill'ine git.
2. Parser: `yeni-parser-ekle` skill'ine yönlendir.
3. `tools/<domain>.py` oluştur: `register(mcp)` içinde nested `@mcp.tool` closure;
   `@auth_guarded` iç decorator; oturum-düşme sentinel'i (`name="TCKimlikNo"`); liste
   zarfı (`limit` default 50, `0`=sınırsız, `count`/`total`/`truncated`) —
   `tools/_common.py` ve mevcut `tools/allergies.py` örnek.
4. `server.py`: `from .tools import (...)` bloğuna ekle VE doğru grupta `<mod>.register(mcp)`
   çağır; `annotations={"readOnlyHint": True, "openWorldHint": True}` (yan etki yoksa).
5. Test: sentetik fixture (`tests/fixtures/<ad>_sample.html`, `<!-- SENTETİK -->`
   başlığı, PHI yok); liste tool'u için `test_tools_smoke.py::_MODULES`'a ekle + adı
   `enabiz_list_*` (ikisi de yoksa sıfır kapsam); parser robustness için nav-only ve
   tbody'siz vaka.
6. Doğrula: `uv run pytest && uv run ruff check`.
7. `surum-guncelle` skill'ini çalıştır.

### 2.2 `yeni-parser-ekle`
Standart iskelet: `soup.select_one("#tblXxx")` (SADECE tam id, fallback yok) → yoksa
`return []` → `for tr in _rows(table)` → satır guard `if len(tds) < N or not any(tds[:N]):
continue` (N gerçek kolon sayısının ALTINDA taban) → `_cell(tds, i)` / gerekli alan
`_cell(tds, 0) or ""`. Değerler hep `str`. Pydantic model: İngilizce snake_case alan
adı + Türkçe `description`. Çok-tablolu sayfa: modül-seviye `(table_id, slug)` tuple'ı,
slug ASCII Türkçe. onclick token: `_XXX_RE` + `_row_token`, virgül/tırnak içeren
kolonda son tırnaklı argümana çapala. Kart-grid sayfa: CSS class seçici (`_rows` değil).
`list[dict]`/`dict` dönenler `.model_dump()`; `list[Model]` dönen instance ekler.
İstisna: `parse_prescriptions` bilerek `tds`'i doğrudan indeksler (onclick regex için
ham `<td>` gerekli) — standart iskelet mutlak değil.

### 2.3 `endpoint-kesfet` (güvenli)
`discovery.py` saf/ağsız, MCP tool değil; canlı tarama `scripts/discover.py`. TTY
kapısı `login_start`'tan ÖNCE (SMS tetikler). Yalnız sayfanın kendi `$.ajax`
endpoint'leri taranır, `<a href>` izlenmez. `_WRITE_TOKENS` denylist (write her zaman
kazanır); `Goruntule` gibi belirsiz fiiller bilerek `_READ_TOKENS` DIŞINDA → "unknown"
→ replay edilmez. Bu listeleri düzenlemek canlı PHI sistemine ne gönderileceğini
değiştirir. Sadece param ADLARI çıkarılır, değer değil. Ham HTML → `docs/findings/raw/`
`chmod 0o600`, gitignore'da; yalnız yapısal `discovery-report.md` commit'lenir.
Promosyon (endpoint→tool) MANUEL ve çok adımlı.

### 2.4 `surum-guncelle`
Bir feature/faz değişikliğinden sonra tutarlılık: `docs/STATUS.md` tool/alan sayıları
+ durum tablosu + `Son güncelleme:` tarihi; `README.md` tool sayısı ve listesi;
commit gövdesinde güncel test sayısını yaz (sabit değil, o anki `pytest` çıktısı);
`Co-Authored-By` trailer. `docs/notes/decisions.md` yalnız gerçek bir mimari karar
varsa (append-only ADR).

## 3. `.claude/settings.json`

Yalnız `permissions.allow`. Dahil (salt-okunur/rutin): `uv run pytest*`, `uv run ruff*`,
`uv sync`, `git status`/`git diff`/`git log`/`git show`, `ls`/`cat`/`grep`/`rg`/`find`
tarzı okuma. HARİÇ (yan etkili — allowlist'e girmez): `enabiz-mcp` sunucusunu
çalıştırma, `.env`/oturum/`session.json`/`pending.json` dosyalarına dokunan komutlar,
`git commit`/`push`, `rm`. Hook YOK.

## 4. `.claude/agents/guvenlik-denetcisi.md`

Salt-okunur denetçi (düzeltme yapmaz), diff'i tarar, iki rolü birleştirir:
- **PHI:** repoya sızan gerçek sağlık verisi/gerçek TCKN/telefon/e-posta; loglanan PHI;
  gitignore dışına düşmüş ham HTML (`docs/findings/raw/` dışı); `.env` içeriği;
  fixture'da PHI (`<!-- SENTETİK -->` yok).
- **Salt-okunur invaryant:** yeni yazma-ucu çağrısı; eksik/yanlış `readOnlyHint`;
  geri gelmiş `or soup.find("table")`; değer alanı int/float'a çevrilmiş;
  `session_status` dürüstlüğü ihlali; `tr_lower` slug'a uygulanmış.
Bulguları önem sırasıyla raporlar.

## 5. `.claude/commands/*.md`

Dört ince slash komut — her biri ilgili skill'i çağırır: `/yeni-tool`, `/yeni-parser`,
`/kesfet`, `/surum`. İçerik minimal (skill'e devret); mantık skill'de yaşar.

## Kapsam dışı (YAGNI)
- Hook (PostToolUse/Stop) yok — sadece allowlist.
- Ayrı iki denetçi ajan yerine tek birleşik `guvenlik-denetcisi`.
- MCP eklenmez (repo zaten MCP sunucusu). `.mcp.json` gitignore'da — dokunulmaz.

## Doğrulanmış çekinceler (harita doğrulama pasından)
1. "`_cell` kullan, `tds`'i indeksleme" mutlak DEĞİL — `parse_prescriptions` bilerek
   ham `<td>` indeksler. Kural standart iskelete özgü.
2. Commit test sayısı ("208 test" gibi) illüstratif — o anki gerçek sayıyı yaz.
3. "15 parser" (fallback kaldırılan) vs "19 tablo-parser" (tek sapan
   `parse_prescriptions`) — ikisi de doğru, farklı şeyler; `a074eee` gövdesi ikisini de
   yazar. "Tablo parser'ları `_rows()` paylaşır" de, "tüm parser'lar" DEME (kart-grid/
   serbest-metin parser'lar `_rows` kullanmaz).

## Kabul kriterleri
- `CLAUDE.md` kökte, Türkçe, ince; her teknik madde çapalı.
- 4 skill dosyası geçerli frontmatter + numaralı checklist ile.
- `settings.json` yalnız allowlist, yan etkili komut içermez, geçerli JSON.
- `guvenlik-denetcisi.md` geçerli agent frontmatter ile.
- 4 slash komut skill'lere devreder.
- Hiçbir dosyada PHI/gerçek kimlik yok; commit `.mcp.json`'a dokunmaz.
- Commit Conventional + Türkçe + trailer.
