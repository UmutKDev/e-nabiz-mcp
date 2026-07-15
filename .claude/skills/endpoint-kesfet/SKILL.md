---
name: endpoint-kesfet
description: Use when discovering or probing E-Nabız portal endpoints to find new read-only data sources — running scripts/discover.py safely, respecting the write-endpoint denylist, capturing raw HTML without leaking PHI, and understanding that endpoint→tool promotion is manual. Invoke before adding a tool for an endpoint not already in docs/findings/.
---

# Endpoint keşfet (güvenli)

Yeni salt-okunur veri uçlarını bulmak için portalı tarar. Bu CANLI bir PHI sistemine
karşı çalışır — kırmızı çizgi: **hiçbir yazma/aksiyon ucu replay edilmez** ve **hiçbir
PHI commit'lenmez**.

## Mimari

- **`src/enabiz_mcp/discovery.py`** saf/ağsız mantık (test edilebilir, `test_discover.py`);
  **MCP tool DEĞİL, `server.py`'de kayıtlı değil.** Yeni test edilebilir mantık buraya.
- **`scripts/discover.py`** canlı tarama + giriş + I/O. `scripts/` bir paket değildir —
  test/başka betikten `importlib` ile dosya yolundan yüklenir (`capture_faz3b.py:34-40`).

## Kurallar

1. **TTY kapısı `login_start`'tan ÖNCE.** `login_start` SMS tetikler; stdin bir TTY
   değilse giriş adımına GİRME (otomatik koşuda başıboş SMS olmasın) —
   `scripts/discover.py`. Şifre `.env`'den `auth` okur (betik görmez); OTP `getpass` ile.
2. **Yalnız sayfanın kendi `$.ajax` uçları taranır.** `<a href>` linkleri İZLENMEZ
   (`discovery.py:8-11`).
3. **`_WRITE_TOKENS` denylist'i, `classify_action`'da write her zaman kazanır.**
   `Goruntule` gibi belirsiz fiiller `_READ_TOKENS` DIŞINDA bırakılmıştır (yazma modalı
   açabilir) → "unknown" → replay edilmez (`discovery.py:56-67`). Bir fiili
   `_READ_TOKENS`'a eklemek, önceden hiç dokunulmayan bir ucu canlı sistemde replay
   edilir hâle getirebilir — güvenlik-kritik, dikkatle.
4. **Replay yalnızca:** read + honeypot değil + her param değeri biliniyor
   (boş/yıl/token/bilinen enum); değilse `ok=False` (`plan_replay` `:274-301`). `$.ajax`
   metodu belirtilmemişse **POST** kabul edilir (`discovery.py:163-164`) — jQuery'nin
   gerçek varsayılanı GET olsa da kod temkinli olarak POST'a düşer.
5. **Yalnız param ADLARI çıkarılır, değer ASLA** — PHI yakalanmaz. Yıl parametreleri 4
   farklı ad çiftiyle gelir; yeni varyantı `YEAR_START_PARAMS`/`YEAR_END_PARAMS`'a ekle,
   uç-bazlı koda değil (`:48-49`).
6. **Ham HTML → `docs/findings/raw/`**, `chmod 0o600`, gitignore'da (PHI). Yalnız
   **yapısal** `docs/findings/discovery-report.md` commit'lenir (uç, metod, param adları,
   status, byte, content-type, kap seçici, satır sayısı, verdict — gövde/önizleme YOK).
   Rapora operatörün kendi TCKN'si sızarsa yazımdan önce abort
   (`scripts/discover.py:256-258`).

## Promosyon manueldir
Keşif yalnız yapıyı tarar ve PHI-güvenli kaydeder. Bir ucu tool'a çevirmek ÇOK ADIMLI ve
ELLE'dir: parser yaz + `server.py`'de kaydet. `discovery.py` çalışma-zamanında src'de
hiçbir şey tarafından import edilmez — otomatik bağlama bekleme. Devamı için
`yeni-tool-ekle` skill'i.

## Kaçınılacaklar
- `_WRITE_TOKENS`/`_READ_TOKENS`'ı gerekçesiz düzenleme — replay davranışını değiştirir.
- Rapora hücre değeri / gövde / önizleme yazma.
- `docs/findings/raw/` veya `samples/`'ı commit'leme (gitignore'da; PHI). Ama
  `discovery-report.md`, `endpoints.md`, `data-models.md`, `auth-flow.md` commit'lenir —
  tüm `findings/` dizini yok sayılı DEĞİL.
