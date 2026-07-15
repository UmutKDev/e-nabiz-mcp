# E-Nabız MCP

E-Nabız (T.C. Sağlık Bakanlığı **Kişisel Sağlık Sistemi**) verilerinize bir LLM
üzerinden erişmek için **yerel** bir MCP (Model Context Protocol) sunucusu.

> ⚠️ **Kişisel kullanım.** Bu araç yalnızca **kendi hesabınıza, kendi kimlik
> bilgilerinizle** erişmeniz içindir. Hassas sağlık verisi (PHI) işler; yerel
> `stdio` üzerinden çalışır, hiçbir veriyi harici servise göndermez.

## Durum

🟢 Çekirdek çalışıyor: **37 tool / 20 veri alanı**, salt-okunur. İlerleme:
[`docs/STATUS.md`](docs/STATUS.md).

## Amaç ve iyi niyet beyanı

Bu proje **kişisel kullanım ve öğrenme amacıyla** yazıldı: kendi sağlık geçmişinize
bir LLM üzerinden anlamlı şekilde erişebilmek ("son beş yılda hangi tahlillerim
referans dışıydı?") ve modern bir ASP.NET portalının XSRF + 2FA akışının nasıl
çalıştığını anlamak. Bir güvenlik kontrolünü aşma, veri toplama ya da başkasının
verisine erişme aracı **değildir**.

Bu bir niyet beyanından ibaret olmasın diye, her madde kodda doğrulanabilir:

| İlke | Kodda karşılığı |
|---|---|
| **Yalnızca kendi veriniz** | Kimlik bilgileri yalnız `.env`'den okunur, tool argümanı değildir (LLM bağlamına hiç girmez). Başka bir hesaba erişecek bir yol yoktur — portal zaten kendi TC kimliğinize gelen SMS'i ister. |
| **Salt-okunur** | Hiçbir tool sağlık verinize yazmaz: e-Nabız'ın yazma uçlarına (`/Sil`, `/Kaydet`, `/Iptal` …) dokunulmaz. Bu bir söz değil, test edilen bir invaryant — keşif tarayıcısı bir yazma ucuna dokunursa suite kasten patlar (`tests/test_discover_scan.py:45`). Randevu tool'ları (e-Nabız ve MHRS) randevu **almaz/iptal etmez**. MHRS tarafında ayrıca bir **çalışma-zamanı kapısı** var: yazma sınıfı bir uca gidilirse istek `WriteNotAllowed` ile durur. |
| **Dürüst tool anotasyonları** | 37 tool'un 35'i `readOnlyHint: True`. İşaretlenmeyen 2'si `login_start`/`login_verify` — çünkü gerçekten yan etkileri var (telefonunuza SMS gider, oturum dosyası yazılır). Her şeye "salt-okunur" damgası vurulmadı. |
| **Güvenlik kontrolleri atlatılmaz** | reCAPTCHA çözülmez, SMS OTP kaldırılmaz veya kırılmaz — kod **her zaman** sizin kayıtlı telefonunuza gider ve giriş insan-döngüdedir. Otomasyon, kodu elle girmenin yerine geçer; kontrolün kendisini ortadan kaldırmaz. |
| **Veri sizde kalır** | Yalnız yerel `stdio`. Harici API, telemetri, analytics yok. PDF'ler diskinize `chmod 600` ile iner; içerik LLM'e verilmez, yalnız `{saved_path, byte_size, sha256, content_type}` döner. |
| **Portala saygı** | İstekler arası hız sınırı (`ENABIZ_MIN_INTERVAL`, varsayılan 0.5 sn) — sunucuya yük bindirmemek için. Toplu/hızlı veri çekme aracı değildir. |
| **PHI repoya girmez** | Testler ağ kullanmaz, sentetik fixture ile çalışır. Ham portal yanıtları gitignore'dadır; bulgu dokümanlarına gerçek değer yazılmaz. |

**Resmî değildir.** T.C. Sağlık Bakanlığı veya E-Nabız ile hiçbir bağlantısı, onayı
ya da desteği yoktur. "E-Nabız" adı yalnızca aracın hangi sisteme eriştiğini tarif
etmek için kullanılır.

**Tıbbi tavsiye değildir.** Araç verinizi yalnızca okur ve yapılandırır; örneğin
`out_of_range` alanı basit bir sayısal aralık karşılaştırmasıdır — klinik bir yorum
değil. Sağlığınıza dair kararlarda hekiminize danışın.

Geri mühendislik yalnızca yazarın **kendi hesabına** karşı, kendi verisiyle yapıldı;
bulgular ([`docs/findings/`](docs/findings/)) yapıyı ve alan adlarını belgeler, gerçek
hasta verisi içermez.

## Nasıl çalışır (özet)

E-Nabız portalı ASP.NET Core tabanlıdır ve giriş **antiforgery (XSRF) çift-token**,
**reCAPTCHA** ve **SMS OTP (2FA)** ile korunur.

- **XSRF** tamamen otomatik yönetilir (bkz. [`docs/findings/auth-flow.md`](docs/findings/auth-flow.md)).
- **reCAPTCHA çözülmez; SMS OTP kaldırılmaz** — kod her zaman gerçek telefonunuza gider.
  Giriş **varsayılan olarak insan-döngüde** yapılır: SMS kodunu siz sağlarsınız.
  (Opsiyonel: kendi Mac'inizde iMessage'a düşen kodu, açık izninizle okuma —
  bkz. [`docs/privacy.md`](docs/privacy.md).)

## Kurulum

Repoyu klonlamadan, `uvx` ile (önerilen):

```bash
uvx enabiz-mcp          # PyPI'dan indirir ve stdio sunucusunu başlatır
```

Geliştirme için, repodan:

```bash
uv sync
cp .env.example .env    # TCKIMLIK ve SIFRE'yi doldurun
uv run enabiz-mcp       # stdio MCP sunucusu
```

> ⚠️ **`uvx` ile `.env` ÇALIŞMAZ.** Kimlik bilgilerini aşağıdaki gibi istemcinin
> `env` bloğuyla verin. Sebep: `python-dotenv` `.env`'i **çağıran modülün
> dosyasından** yukarı doğru arar; `uvx` paketi uv önbelleğine kurduğu için o
> arama sizin proje dizininize hiç uğramaz. Repodan `uv run` ile çalışırken
> bulunur (venv repo içindedir), `uvx` ile bulunmaz — ve bu **sessizce** olur:
> hata ancak girişte "ENABIZ_TCKIMLIK ayarlı değil" olarak çıkar. (Ölçüldü.)

### MCP istemci yapılandırması

**Claude Desktop** (`claude_desktop_config.json`) — `uvx` ile:

```json
{
  "mcpServers": {
    "enabiz": {
      "command": "uvx",
      "args": ["enabiz-mcp"],
      "env": {
        "ENABIZ_TCKIMLIK": "<T.C. kimlik no>",
        "ENABIZ_SIFRE": "<portal şifresi>"
      }
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add enabiz \
  --env ENABIZ_TCKIMLIK=<T.C. kimlik no> \
  --env ENABIZ_SIFRE=<portal şifresi> \
  -- uvx enabiz-mcp
```

Repodan çalıştırıyorsanız (`.env` bu durumda okunur, `env` bloğu gerekmez):

```json
{
  "mcpServers": {
    "enabiz": {
      "command": "uv",
      "args": ["--directory", "/mutlak/yol/eNabizMCP", "run", "enabiz-mcp"]
    }
  }
}
```

Oturum ve inen dosyalar varsayılan olarak `~/.config/enabiz-mcp/` altında,
`chmod 600` ile durur (`ENABIZ_SESSION_PATH` / `ENABIZ_DOWNLOAD_DIR` ile
değiştirilebilir).

## Docker (ghcr.io)

Hazır imaj: **`ghcr.io/umutkdev/e-nabiz-mcp`** (`linux/amd64` + `linux/arm64`).
İmaj yalnızca **kodu** taşır — kimlik bilgisi ve sağlık verisi taşımaz; ikisi de
çalışma zamanında sizin diskinizden bağlanır.

```bash
mkdir -p ~/enabiz-mcp-data          # ÖNCE siz oluşturun (aşağıdaki nota bakın)

docker run -i --rm --init \
  --user "$(id -u):$(id -g)" \
  -v ~/enabiz-mcp-data:/data \
  -v "$PWD/.env:/app/.env:ro" \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  ghcr.io/umutkdev/e-nabiz-mcp:latest
```

Bayrakların hepsi gereklidir, dekoratif değil:

| Bayrak | Neden |
|---|---|
| `-i` | **Şart.** stdio sunucusu; stdin kapalıysa EOF görüp anında çıkar. `-d` ile ASLA çalıştırmayın. |
| `-v .env:/app/.env:ro` | Kimlik bilgilerinin **tek doğru yolu**. `/app` dışına bağlarsanız sessizce bulunmaz. |
| `-v ~/enabiz-mcp-data:/data` | Oturum kalıcılığı + inen PDF'ler. Yoksa her yeniden başlatma **gerçek bir SMS OTP yakar**. |
| `--user` | Linux'ta bind-mount sahipliği. macOS'ta zararsız. |
| `--init` | PID 1'deki Python'un varsayılan SIGTERM işleyicisi yoktur; `docker stop` bunsuz 10 sn bekler. |
| `--read-only` + `--tmpfs` | Sertleştirme; tek yazılabilir yol `/data`. |

**`-e` / `--env-file` KULLANMAYIN.** Ölçüldü: `--env-file .env` ile başlatılan bir
konteynerde `docker inspect` çıktısındaki `.Config.Env` alanı `ENABIZ_SIFRE` ve
`ENABIZ_TCKIMLIK` değerlerini **düz metin** gösterir. T.C. Kimlik No geri alınamaz;
mount edilen dosya `docker inspect`te görünmez. Bu yüzden `.env` **dosya olarak**
bağlanır.

**Neden `/app/.env`?** `.env`'i bulan şey `WORKDIR` değil, **venv'in konumudur**:
python-dotenv'in `find_dotenv()`'i çağıran modülün dosyasından yukarı yürür
(`/app/.venv/lib/python3.13/site-packages/enabiz_mcp/config.py` → … → `/app`).
`.env`'i `/data`'ya bağlarsanız **hiç okunmaz** ve hata ancak login sırasında
"ENABIZ_TCKIMLIK ayarlı değil" olarak yüzeye çıkar. (Bu, tasarım sırasında
ölçülerek doğrulandı.)

**`~/enabiz-mcp-data`'yı neden önce siz oluşturuyorsunuz?** Linux'ta Docker eksik
bir bind-mount kaynağını **root'a ait** olarak yaratır. `--user` ile çalışan sunucu
oraya yazamaz ve hata `enabiz_login_start`'ta, **SMS gönderildikten sonra** patlar —
yani her denemede gerçek bir OTP yakılır. Dizin önceden varsa sorun oluşmaz.

### MCP istemci yapılandırması (Docker)

`$(id -u)` ve `~` JSON içinde **genişlemez** — `id -u; id -g` çıktısını ve mutlak
yolları elle yazın:

```json
{
  "mcpServers": {
    "enabiz": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--init",
               "--user", "501:20",
               "-v", "/Users/KULLANICI/enabiz-mcp-data:/data",
               "-v", "/Users/KULLANICI/eNabizMCP/.env:/app/.env:ro",
               "--read-only", "--tmpfs", "/tmp",
               "ghcr.io/umutkdev/e-nabiz-mcp:latest"]
    }
  }
}
```

İnen PDF'ler konteynerde `/data/downloads` altına yazılır; host'ta
`~/enabiz-mcp-data/downloads/` olarak, `chmod 600` ile sizde kalır.

## Giriş akışı

`enabiz_login_start` → telefona gelen kodu `enabiz_login_verify`'a girin. Oturum yerel
olarak saklanır ve süresi (~30–60 dk) dolana dek yeniden kullanılır. Oturum düşerse veri
tool'ları `error: "auth_required"` döner; yeniden giriş yapın.

## Tool'lar (37)

**Oturum:** `enabiz_login_start` · `enabiz_login_verify` · `enabiz_session_status`

**Özet:** `enabiz_get_health_summary` (profil + alerji + tanı/aşı/ilaç/ziyaret sayıları + randevular, tek çağrı)

**Tahliller:** `enabiz_list_lab_tests` · `enabiz_get_lab_trend`

**Reçete & ilaç:** `enabiz_list_prescriptions` · `enabiz_get_prescription_detail` ·
`enabiz_list_optical_prescriptions` · `enabiz_list_device_prescriptions` ·
`enabiz_list_medications` · `enabiz_get_drug_leaflet` · `enabiz_get_drug_usage_history`

**Klinik:** `enabiz_list_reports` · `enabiz_list_allergies` · `enabiz_list_diagnoses` ·
`enabiz_get_diagnosis_detail` · `enabiz_list_chronic_disease_followups` ·
`enabiz_list_vaccinations` · `enabiz_list_discharge_summaries` · `enabiz_list_pathology`

**Radyoloji:** `enabiz_list_radiology_studies` · `enabiz_get_radiology_report` ·
`enabiz_get_radiology_image_link`

**Ziyaret & randevu:** `enabiz_list_hospital_visits` · `enabiz_get_visit_detail` ·
`enabiz_list_appointments` (salt-okunur; almaz/iptal etmez)

**MHRS (randevu sistemi):** `enabiz_mhrs_list_provinces` · `enabiz_mhrs_list_districts` ·
`enabiz_mhrs_list_clinics` · `enabiz_mhrs_list_upcoming` · `enabiz_mhrs_list_history`

> MHRS (`prd.mhrs.gov.tr`) e-Nabız'dan **ayrı bir sistemdir**; e-Nabız'ın "Randevu Al"
> düğmesinin arkasındaki SSO devriyle bağlanılır. `enabiz_list_appointments` e-Nabız'ın
> HTML tablosunu okur; MHRS tool'ları API'nin kendisini okur ve `hrn` (hasta randevu
> numarası) döndürür — tabloda olmayan, iptal için gereken anahtar.
>
> **Bu tool'lar da randevu almaz/iptal etmez** (hepsi `readOnlyHint: True`). Randevu
> alma iki-adımlı onayla ayrı bir fazda gelecek; bkz. [`docs/STATUS.md`](docs/STATUS.md)
> ve [`docs/notes/decisions.md`](docs/notes/decisions.md) D7.

**Profil & idari:** `enabiz_get_profile` · `enabiz_list_insurance` ·
`enabiz_list_materials_devices` · `enabiz_list_emergency_notes`

**Belge indirme:** `enabiz_download_document(kind=...)` — `lab` · `pathology` ·
`discharge` · `radiology` PDF'lerini tek uçtan indirir.

> Tüm veri tool'ları **salt-okunur**. PDF tool'ları dosyayı `ENABIZ_DOWNLOAD_DIR`'e
> (varsayılan `~/.config/enabiz-mcp/downloads`, `chmod 600`) kaydeder ve içerik yerine
> `{saved_path, byte_size, sha256, content_type}` döner.

## Test

```bash
uv run pytest           # ağ yok; sentetik fixture (PHI'sız)
```

## Gizlilik

Bkz. [`docs/privacy.md`](docs/privacy.md). Kimlik bilgileri yalnızca `.env`'de;
oturum yerel dosyada sıkı izinle saklanır; ham sağlık verisi loglanmaz veya
commit edilmez.

## Kullanım şartları

E-Nabız'a otomatik/programatik erişim, portalın kullanım şartlarına tabi olabilir.
Bu araç kişisel, meşru kendi-verinize-erişim amacıyla sağlanır; sorumluluk kullanıcıdadır.
