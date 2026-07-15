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

### D7 — Salt-okunur kapsamı daraltıldı: MHRS randevu yazma uçları kabul edildi
*2026-07-15*

**Karar.** Proje artık **iki sistemi** kapsıyor ve salt-okunur kuralı sisteme göre
ayrışıyor:

- **E-Nabız (KSS) sağlık verisi: SALT-OKUNUR KALIR.** Tanı, tahlil, reçete, rapor,
  aşı, radyoloji — hiçbiri yazılmaz. `discovery.py`'deki `_WRITE_TOKENS` denylist'i
  (`RandevuAl`/`ManuelRandevu` dahil) ve `tests/test_discover_scan.py:44-45`
  tripwire'ı **aynen duruyor**; e-Nabız keşif tarayıcısı hâlâ hiçbir yazma ucuna
  dokunmuyor.
- **MHRS (randevu sistemi): YAZMA AÇIK.** Randevu alma ve iptal, `prd.mhrs.gov.tr`
  API'si üzerinden, `readOnlyHint: False` taşıyan ve **iki-adımlı onay** gerektiren
  tool'larla yapılır.

**Gerekçe.** Randevu almak kullanıcının kendi hesabında, kendi adına, portalın kendi
resmî SSO akışıyla yaptığı meşru bir işlem. "Bu hastanede yarın boş slot var mı"
sorusunu cevaplayıp randevuyu kullanıcıya elle aldırmak, aracın değerinin yarısını
keyfi biçimde kesiyordu.

**İki-adımlı onay zorunlu — teknik değil, sonuçsal bir gerekçe.** T.C. Sağlık
Bakanlığı politikası (saglik.gov.tr TR,94138): randevuya gitmeyen/iptal etmeyen
**aynı branştan 15 gün** randevu alamaz. (Para cezası iddiası yalandır — AA Teyit
"Yanlış" damgalı; MHRS işlemleri ücretsiz.) Tek adımlı bir `book(slot_id)` tool'unda
LLM'in halüsinasyon slot id'siyle randevu alması, kullanıcıya gerçek bir branş yasağı
yazdırır. Bu yüzden:

- `book_prepare(slot_id)` slotu MHRS'den **doğrular**, insan-okunur özet + tek
  kullanımlık `confirm_token` döner, hiçbir şey yazmaz.
- `book_confirm(confirm_token)` yazar; token `prepare`'den gelmemişse reddeder.

Böylece kullanıcının onayladığı şey uydurma değil, doğrulanmış bir randevudur.
Desen yeni değil: `login_start`/`login_verify` aynısı.

**Sınıflandırıcı tool'ları bağlamaz.** `mhrs/discovery.py`'deki read/write sınıflaması
keşif raporunu dürüst tutmak ve *tarayıcının* yazma ucuna dokunmasını engellemek
içindir. Tool'lar uçlarını elle, insan incelemesiyle sabitler — promosyon manueldir.
Çalışma zamanında `api_client(..., allow_write=True)` açık bir niyet beyanıdır:
kaza eseri yazmayı imkânsız, bilerek yazmayı tek parametre yapar.

**Kabul edilen riskler.** `robots.txt` `Disallow: /api/` (statik bundle izinli,
`/api/` değil) — kullanıcı kendi hesabına kendi adına eriştiği için devam edildi.
`RNDS1000` anti-bot kilidi kullanıcıyı online randevudan çıkarabilir → slot arama
poll döngüsü yapmaz, RNDS1000'de retry YOK. `LGN2001` tek-oturum → programatik giriş
kullanıcının telefondaki oturumunu düşürebilir. Hepsi `docs/findings/mhrs.md`'de.

**Kapsam dışı — değişmedi.** reCAPTCHA çözülmez (invaryant #4). Buna gerek de yok:
`captchaKey` yalnız parola login'inde; kullanılan `enabizToken` SSO zincirinde
CAPTCHA yoktur.

### D8 — MCP Apps (ext-apps) katmanı: panel PHI'yı model bağlamından çıkarır
*2026-07-16*

**Karar.** `io.modelcontextprotocol/ui` uzantısı eklendi. Panel render edebilen
istemcilerde liste tool'ları kayıt DEĞERLERİNİ değil yalnız SAYIYI döner; kayıtlar
`enabiz_ui_data` (`visibility: ["app"]`) ile panele, modeli baypas ederek gider.
Panel render edemeyen istemcilerde bugünkü metin çıktısı byte-byte aynı kalır.

**Gerekçe — panel bir süs değil, invaryant #3'ün uygulaması.** "PHI, LLM bağlamına
girmez" kuralı bugüne dek yalnız *indirme* tool'larında tutuluyordu
(`downloads.py` içerik yerine `{saved_path, byte_size, sha256, content_type}` döner).
Liste tool'ları kuralı çiğniyordu: `enabiz_list_lab_tests` tahlil değerlerini
doğrudan model bağlamına yazıyor. Panel, bu boşluğu kapatan ilk mekanizmadır.

**Yön kasıtlı: belirsizlik metin yoluna düşer.** `ui.app_capable()` bağlam yoksa
veya istemci uzantıyı ilan etmemişse `False` döner (ölçüldü). Böylece en kötü
ihtimalle PHI bugünkü gibi modele gider — yani REGRESYON YOK. Ters yön ("panel yok
ama veri de yok") mümkün değil.

**`ctx` tool imzasına EKLENMEZ.** `app_capable()` bağlamı `get_context()` ile alır.
İmzaya `ctx: Context` eklemek `tests/test_tools_smoke.py`'ı `TypeError` ile kırdı —
ölçüldü. Testi düzeltmek yanlış cevaptı: mevcut testin kırılması, metin yolunun
çağrı sözleşmesini bozduğumuzun kanıtıydı.

**Vendor'lanmış JS varlığı — D1 ihlali DEĞİL.** `src/enabiz_mcp/ui/vendor/ext-apps.js`,
`@modelcontextprotocol/ext-apps@1.7.4`'ün tarayıcı paketidir (MIT). Repoda npm
toolchain'i YOK ve olmayacak; bu bir JS *varlığı*, JS *toolchain'i* değil. D1
TypeScript SDK'sını sunucu dili olarak reddetti — sunucu tarafı hâlâ saf Python
(`fastmcp.apps`, ek bağımlılık gerekmedi). Vendor zorunlu: iframe CSP'si CDN
import'unu engeller (paket blank render eder) ve privacy.md §1-2 dış egress
yasaklar. Kaynaklar `ui://` ile protokol üzerinden servis edilir — HTTP sunucusu
yok, D3 (stdio-only) korunur. Widget CSP'si `connectDomains: []` — iframe hiçbir
yere bağlanamaz.

**Türkçe büyütme CSS'e bırakılmaz.** `text-transform: uppercase` `lang`'a bağlıdır
ve sessizce `NIS`/`DERI TESTI` üretir (doğrusu `NİS`/`DERİ TESTİ`). Ölçüldü —
tarayıcıda bu hâliyle göründü. Büyütme JS'te açık `toLocaleUpperCase("tr")` ile
yapılır; ay kısaltmaları zaten büyük sabitlenir. D6'nın ı/i tuzağının CSS hâli.
Tripwire: `tests/test_ui_resources.py`.

**Açık kalan ölçüm.** "`callServerTool` sonucu modele gitmez" iddiası ext-apps
dokümanının beyanıdır; CANLI ÖLÇÜLMEDİ. Ölçüm aksini gösterirse app-only PHI
iddiası geri alınır ve karma moda düşülür (panel görselleştirir, PHI bugünkü gibi
modele de gider). Bu ölçüm yapılana dek D8'in PHI iddiası KANITLANMAMIŞ sayılır.

**Kapsam dışı.** Uzak/HTTP transport (D3) — dolayısıyla ChatGPT/Claude-web bu
sunucuya bağlanamaz; engel lehçe değil (ChatGPT 2026-02'den beri standart
`_meta.ui.*` okuyor), transport. Claude Code panel render etmez (terminal, iframe
yüzeyi yok) → metin yolu. `prefab_ui`/`fastmcp[apps]` alınmadı (FastMCP kendi
dokümanında Prefab için "sık kırıcı değişiklik" uyarıyor). `mcp-ui` alınmadı —
resmi uzantı varken ikinci soyutlama katmanı.
