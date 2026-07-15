"""MHRS (Merkezi Hekim Randevu Sistemi) entegrasyonu.

E-Nabız'daki "Randevu Al" düğmesi bir SSO devir zinciri başlatır: e-Nabız bir
`enabizToken` basar, MHRS onu JWT'ye çevirir, ve gerçek randevu işlemleri
`prd.mhrs.gov.tr` API'sinde olur. Bu alt paket o ikinci sistemi kapsar.

E-Nabız tarafından iki temel farkı vardır:

- **JSON API**, HTML değil. `parsers.py` (BeautifulSoup) buraya uygulanmaz;
  yanıt modelleri `mhrs/models.py`'dedir.
- **Bearer JWT**, cookie değil. `auth.session_alive()` (HTML'de `TCKimlikNo`
  arar) burada anlamsızdır; canlılık `mhrs/auth.py`'de JWT `exp` + 401 ile ölçülür.

Salt-okunur invaryantı: e-Nabız **sağlık verisi** salt-okunur kalır. Yazma
yalnızca MHRS randevu alanında ve yalnızca iki-adımlı onaylı tool'larda yapılır
(bkz. `docs/notes/decisions.md` D7).
"""
