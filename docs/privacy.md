# Gizlilik & güvenlik politikası

Bu proje **hassas kişisel sağlık verisi (PHI)** ve kimlik bilgileriyle çalışır.
Aşağıdaki kurallar bağlayıcıdır.

## Temel ilkeler
1. **Yerel-only.** Sunucu yalnızca yerel `stdio` üzerinden çalışır. Uzak/remote
   transport, harici API, telemetri **yok**.
2. **Veri dışarı çıkmaz.** Hiçbir sağlık verisi, kimlik bilgisi veya oturum jetonu
   üçüncü bir servise gönderilmez.
3. **Kimlik bilgileri yalnızca `.env`.** `ENABIZ_TCKIMLIK` / `ENABIZ_SIFRE` ortam
   değişkenlerinden okunur; koda gömülmez, MCP tool argümanı olarak taşınmaz
   (yani LLM sohbet bağlamına girmez).
4. **Oturum sıkı izinli.** Kimlikli cookie'ler `~/.config/enabiz-mcp/session.json`
   dosyasında `chmod 600` ile saklanır.
5. **Ham PHI loglanmaz.** Loglarda tahlil değerleri, tanılar, kişisel alanlar yer
   almaz; hata mesajları veriyi sızdırmaz.

## Commit edilmeyecekler (`.gitignore`)
- `.env`, her türlü secret
- oturum/cookie dosyaları (`*.session`, `session.json`, `cookies.txt`)
- indirilen ham sağlık verisi / kişisel yanıtlar (`docs/findings/raw/`, `samples/`)

## Güvenlik kontrolleri
- **reCAPTCHA** çözülmez/atlatılmaz (giriş bu adımda captcha-gated değil; bkz.
  `findings/auth-flow.md`).
- **SMS OTP** gerçek bir 2FA'dır ve **kaldırılmaz/kırılmaz**: kod her zaman kullanıcının
  kayıtlı telefonuna gönderilir. Giriş **varsayılan olarak insan-döngüdedir** (kod
  terminale `getpass` ile girilir; operatör script'leri etkileşimsiz terminalde giriş
  başlatmaz).
- **Opsiyonel iMessage-OTP:** Kullanıcı açıkça izin verirse ve kendi Mac'inde Full Disk
  Access ile iMessage MCP erişilebilirse, OTP kullanıcının **kendi cihazından** (yalnız
  ilgili e-Nabız OTP mesajı) okunabilir. Bu, aynı hesap sahibinin OTP'yi elle girmesinin
  otomasyonudur — kontrolün atlatılması değil (kod yine gerçek telefona gider). Başka
  mesajlar okunmaz; izin oturuma özeldir ve kullanıcı tarafından verilir.

## Dokümantasyon kuralı
`docs/` içindeki bulgu dosyalarına **gerçek** token/cookie/kimlik/hasta değeri
yazılmaz; yalnızca yapı, alan adları ve anonim/uydurma örnekler.

## Uygulama durumu (Faz 4 — doğrulandı)
- ✅ `chmod 600` oturum/pending dosyalarında (`save_session`/`_save_pending`);
  `tests/test_auth.py::test_session_roundtrip_and_permissions` ile test edilir.
- ✅ **Hız sınırı:** istekler arası ≥ `ENABIZ_MIN_INTERVAL` (varsayılan 0.5 sn) —
  WAF'ı (SAGLIK* cookie) tetiklememek için (`client._Throttle`, test edildi).
- ✅ **PHI konsola/sohbete basılmaz:** keşif boyunca yalnızca sayım/yapı raporlandı;
  ham HTML yalnızca gitignored `docs/findings/raw/`'a yazıldı.
- ✅ Testler ağ kullanmaz ve sentetik fixture ile çalışır (PHI'sız).
- ✅ **İndirilen PDF'ler** `ENABIZ_DOWNLOAD_DIR`'e (varsayılan `~/.config/enabiz-mcp/
  downloads`) `chmod 600` ile yazılır; PDF içeriği LLM'e/transkripte verilmez, yalnız
  `{saved_path, byte_size, sha256, content_type}` döner.

## Kullanım şartları
E-Nabız'a programatik erişim portal ToS'una tabi olabilir. Araç kişisel,
kendi-verinize-meşru-erişim amaçlıdır.
