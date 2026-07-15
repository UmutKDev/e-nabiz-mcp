"""MHRS kimlik doğrulama — e-Nabız SSO devir zinciri.

Üç adım (`docs/findings/mhrs.md`'de tam belgelenmiş):

1. `GET enabiz.gov.tr/Randevu/RandevuAl?ID=<kişiye-özel>&vasiOnay=False`
   → gövdede `...#/?enabizToken=<uuid>&lang=tr-TR`
2. `POST prd.mhrs.gov.tr/api/vatandas/enabiz/login` `{enabizToken, islemKanali}`
   → `data.jwt`
3. Sonraki her çağrı: `Authorization: Bearer <jwt>`

**CAPTCHA yoktur** — `captchaKey` yalnız parola login'indedir (`vatandas/login/v2`).
Bu zincir portalın kendi resmî devir akışıdır; hiçbir güvenlik kontrolü atlatılmaz
(invaryant #4).

**JWT insan panosundan geçmez.** Zinciri kod koşturur; `MHRS_JWT` env değişkeni veya
kopyala-yapıştır YOKTUR. Emsal `scripts/discover.py:105` OTP'yi `getpass` ile alır —
sırrı insandan uzak tutmak kasıtlı bir tasarım; 20 saat geçerli, refresh'siz, iptal
edilemez bir bearer'ın sohbete/panoya düşmesi invaryant #3'ün koruduğu tek yüzeydir.
"""

from __future__ import annotations

import base64
import binascii
import dataclasses
import json
import re
import time

import httpx

from .. import auth as enabiz_auth
from ..config import Config

# e-Nabız tarafı — token basım zinciri
RANDEVULARIM_PAGE = "/Home/Randevularim?randevuAl=1"
TOKEN_MINT_PATH = "/Randevu/RandevuAl"

# MHRS tarafı
LOGIN_PATH = "vatandas/enabiz/login"
# Bundle'daki resolver viewport genişliğine bakar (>=990 "lg" → soneksiz). Başsız bir
# istemci için sabit "lg" doğru: sunucu zaten `VATANDAS_ENABIZ`'e normalize ediyor.
ISLEM_KANALI = "VATANDAS_ENABIZ"

# JWT süresi dolmadan bu kadar saniye önce yenile (saat kayması + uçuş süresi payı).
_EXPIRY_SKEW = 120.0

_TOKEN_RE = re.compile(r"enabizToken=([0-9a-fA-F-]{36})")
_PERSON_ID_RE = re.compile(r"/Randevu/RandevuAl\?ID=(\d+)", re.IGNORECASE)


class MhrsError(RuntimeError):
    """MHRS `success: false` döndü. `kodu` sunucunun hata kodu (ör. RND4105)."""

    def __init__(self, message: str, kodu: str | None = None) -> None:
        super().__init__(message)
        self.kodu = kodu


class MhrsAuthRequired(MhrsError):
    """MHRS oturumu yok / süresi dolmuş / başka cihazda sonlandırılmış."""


class MhrsRateLimited(MhrsError):
    """RNDS1000 — anti-bot kilidi.

    **ASLA retry edilmez.** MHRS sorgu sıklığını sezgisel izler ve eşiği aşan
    kullanıcıyı ONLINE randevudan tamamen çıkarıp Alo 182'ye yönlendirir. Yeniden
    denemek kilidi derinleştirir; kayıp hız değil, ERİŞİMDİR.
    """


@dataclasses.dataclass(frozen=True)
class MhrsSession:
    """Canlı MHRS oturumu — JWT ve son kullanma zamanı (unix saniye)."""

    jwt: str
    exp: float

    @property
    def expired(self) -> bool:
        return time.time() >= self.exp - _EXPIRY_SKEW


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def jwt_expiry(token: str) -> float | None:
    """JWT payload'ındaki `exp`'i (unix saniye) okur; okunamazsa None.

    İmza DOĞRULANMAZ — bunu yapmıyoruz ve yapmamalıyız: token bize güvendiğimiz bir
    kanaldan geliyor ve doğrulayacak anahtar bizde yok. `exp` yalnız "ne zaman
    yenileyeyim" sorusu için okunur, yetki kararı için değil.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)  # base64url padding
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
    except (binascii.Error, ValueError, json.JSONDecodeError):
        return None
    exp = data.get("exp")
    return float(exp) if isinstance(exp, (int, float)) else None


# --------------------------------------------------------------------------- #
# Adım 1 — token basımı (e-Nabız tarafı)
# --------------------------------------------------------------------------- #
def scrape_person_id(client: httpx.Client) -> str:
    """`/Home/Randevularim?randevuAl=1` sayfasından kişiye özel `ID`'yi kazır.

    Bu değer PHI'dir ve SABİT KODLANAMAZ — her hesapta farklıdır.
    """
    html = client.get(RANDEVULARIM_PAGE).text
    if 'name="TCKimlikNo"' in html:  # login'e yönlendirildi
        raise enabiz_auth.AuthRequired("Randevularım: e-Nabız oturumu düşmüş.")
    m = _PERSON_ID_RE.search(html)
    if not m:
        raise MhrsError(
            "Randevularım sayfasında RandevuAl bağlantısı bulunamadı — sayfa yapısı "
            "değişmiş olabilir."
        )
    return m.group(1)


def mint_enabiz_token(client: httpx.Client, person_id: str | None = None) -> str:
    """SSO `enabizToken`'ını bastırır (e-Nabız oturumu gerekir).

    ⚠️ Uç `RandevuAl` ADINI taşır ama randevu ALMAZ — bir SSO token'ı basar; gerçek
    randevu MHRS `randevu-ekle` ile alınır. Yine de yan etkilidir (sunucuda token
    üretir), yani `login_start`/`login_verify` ile aynı sınıftadır: salt-okunur DEĞİL.

    Bu çağrı `enabiz_mcp.discovery._WRITE_TOKENS`'ın adıyla reddettiği bir uca
    bilerek gidiyor. Denylist ORAYA (e-Nabız keşif tarayıcısına) aittir ve
    gevşetilmemiştir; burada insan incelemesinden geçmiş, dar kapsamlı bir istisna
    uygulanıyor. Bkz. `docs/notes/decisions.md` D7.
    """
    pid = person_id or scrape_person_id(client)
    resp = client.get(
        TOKEN_MINT_PATH,
        params={"ID": pid, "vasiOnay": "False"},
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": str(client.base_url)},
    )
    if 'name="TCKimlikNo"' in resp.text:
        raise enabiz_auth.AuthRequired("RandevuAl: e-Nabız oturumu düşmüş.")
    m = _TOKEN_RE.search(resp.text)
    if not m:
        raise MhrsError(
            f"enabizToken alınamadı (HTTP {resp.status_code}) — devir akışı değişmiş olabilir."
        )
    return m.group(1)


# --------------------------------------------------------------------------- #
# Adım 2 — JWT değişimi (MHRS tarafı)
# --------------------------------------------------------------------------- #
def exchange_for_jwt(cfg: Config, enabiz_token: str) -> MhrsSession:
    """`enabizToken`'ı MHRS JWT'sine çevirir."""
    from .client import anon_api_client, unwrap  # döngüsel import'u kır

    with anon_api_client(cfg) as client:
        resp = client.post(
            LOGIN_PATH,
            json={"enabizToken": enabiz_token, "islemKanali": ISLEM_KANALI},
            headers={"Content-Type": "application/json"},
        )
        data = unwrap(resp)

    jwt = data.get("jwt")
    if not jwt:
        raise MhrsAuthRequired("MHRS login yanıtında jwt yok.")
    exp = jwt_expiry(jwt)
    if exp is None:
        # `exp` okunamazsa token'ı süresizmiş gibi KABUL ETME — gözlenen ömür 20 saat,
        # ama uydurma bir sabit yerine kısa bir pencere ver ve zinciri sık koştur.
        exp = time.time() + 3600.0
    return MhrsSession(jwt=jwt, exp=exp)


# --------------------------------------------------------------------------- #
# Oturum kalıcılığı — e-Nabız oturum dosyasında kardeş anahtar
# --------------------------------------------------------------------------- #
def load_mhrs_session(cfg: Config) -> MhrsSession | None:
    """Kayıtlı MHRS oturumunu okur; yoksa/bozuksa None."""
    raw = enabiz_auth.read_session_file(cfg).get("mhrs")
    if not isinstance(raw, dict):
        return None
    jwt, exp = raw.get("jwt"), raw.get("exp")
    if not isinstance(jwt, str) or not isinstance(exp, (int, float)):
        return None
    return MhrsSession(jwt=jwt, exp=float(exp))


def save_mhrs_session(cfg: Config, session: MhrsSession) -> None:
    """MHRS oturumunu e-Nabız cookie'lerinin YANINA yazar (read-modify-write, 0600)."""
    data = enabiz_auth.read_session_file(cfg)
    data["mhrs"] = {"jwt": session.jwt, "exp": session.exp}
    enabiz_auth.write_session_file(cfg, data)


def clear_mhrs_session(cfg: Config) -> None:
    """MHRS oturumunu siler — e-Nabız cookie'lerine DOKUNMAZ."""
    data = enabiz_auth.read_session_file(cfg)
    if data.pop("mhrs", None) is not None:
        enabiz_auth.write_session_file(cfg, data)


def mhrs_session(cfg: Config, *, force: bool = False) -> MhrsSession:
    """Geçerli bir MHRS oturumu döndürür — gerekirse SSO zincirini koşturur.

    Canlılık `session_alive()` ile ÖLÇÜLMEZ: o HTML'de `TCKimlikNo` arar ve JSON
    API'de anlamsızdır. Burada yerel `exp` kontrolü yeterli; sunucu yine de reddederse
    `unwrap` `LGN1004`/401 görüp `MhrsAuthRequired` fırlatır.
    """
    if not force:
        cached = load_mhrs_session(cfg)
        if cached and not cached.expired:
            return cached

    with enabiz_auth.session_scope(cfg) as client:  # e-Nabız oturumu şart
        token = mint_enabiz_token(client)

    session = exchange_for_jwt(cfg, token)
    save_mhrs_session(cfg, session)
    return session
