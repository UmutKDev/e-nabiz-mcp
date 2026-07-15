"""MHRS HTTP istemcileri ve yanıt zarfı.

E-Nabız'ın tek client'ının aksine MHRS üç ayrı client gerektirir, çünkü iki farklı
kök kullanılır ve `httpx` `base_url`'ü sessizce birleştirir:

    base_url="https://prd.mhrs.gov.tr/api/"
    client._merge_url("/vatandas/vatandas-main.js")
      -> https://prd.mhrs.gov.tr/api/vatandas/vatandas-main.js   # YANLIŞ

Yani bundle indirme (origin kökü, kimliksiz) ile API çağrısı (`/api/` kökü, Bearer)
aynı client'ı PAYLAŞAMAZ — sessizce yanlış URL'e giderdi.
"""

from __future__ import annotations

import dataclasses

import httpx

from ..client import build_client
from ..config import Config
from .discovery import API_BASE, BUNDLE_ORIGIN, classify_mhrs_call

_JSON_HEADERS = {"Accept": "application/json, text/plain, */*"}


class ApiBoundaryViolation(RuntimeError):
    """Bundle client'ı `/api/`'ye istek atmaya çalıştı — keşif sözleşmesi ihlali."""


class WriteNotAllowed(RuntimeError):
    """Yazma ucuna `allow_write=True` olmadan istek atıldı."""


def _forbid_api(request: httpx.Request) -> None:
    """Bundle client'ının `/api/`'ye sızmasını MEKANİK olarak engeller.

    Keşif "yalnız public statik varlık okur, kimlik doğrulamaz, `/api/`'ye
    dokunmaz" diye taahhüt ediyor. Bu hook o taahhüdü bir yorumdan bir invaryanta
    çevirir: yanlış bir yol elle geçilirse istek gitmez, exception atar.
    """
    if request.url.path.startswith("/api/"):
        raise ApiBoundaryViolation(
            f"Bundle client'ı /api/'ye istek atamaz (denendi: {request.url.path}). "
            "Statik keşif kimliksizdir; API çağrısı için api_client kullanın."
        )


def _forbid_write(request: httpx.Request) -> None:
    """Yazma sınıfı bir uca `allow_write=False` client ile gidilmesini engeller.

    Salt-okunur invaryantının ÇALIŞMA ZAMANI hâli. E-Nabız tarafında böyle bir kapı
    hiç olmadı — koruma yalnız "hangi ucu elle kodladık" idi. MHRS'de yanlış bir uca
    kaymanın bedeli kullanıcının randevusunu iptal etmek ya da ona 15 günlük branş
    yasağı yazdırmak olduğu için burada mekanik bir kapı var.

    Kapı yasak değil, NİYET beyanı: randevu tool'ları `allow_write=True` geçer.
    """
    path = request.url.path.removeprefix("/api/")
    if classify_mhrs_call(request.method, path) == "write":
        raise WriteNotAllowed(
            f"{request.method} {path} yazma sınıfında; bu client salt-okunur. "
            "Bilerek yazıyorsanız api_client(..., allow_write=True) kullanın."
        )


def bundle_client(cfg: Config) -> httpx.Client:
    """Public statik bundle'ı indirmek için KİMLİKSİZ client.

    Kimlik doğrulama yok, cookie yok, Authorization yok — indirdiği her şey
    tarayıcıya da açık olan statik JS/HTML. `/api/` erişimi hook ile engellidir.
    """
    client = build_client(dataclasses.replace(cfg, base_url=BUNDLE_ORIGIN), cookies=httpx.Cookies())
    client.event_hooks["request"].append(_forbid_api)
    return client


def anon_api_client(cfg: Config) -> httpx.Client:
    """Token DEĞİŞİMİ için kimliksiz API client'ı (`vatandas/enabiz/login`).

    Henüz JWT yok — zaten onu almak için kullanılıyor. `_forbid_write` yok: login
    ucu POST'tur, yani sınıflayıcı onu yazma sayar (doğru) ama bu çağrının amacı
    tam olarak o.
    """
    return build_client(
        dataclasses.replace(cfg, base_url=API_BASE, min_interval=cfg.mhrs_min_interval),
        cookies=httpx.Cookies(),
        extra_headers=_JSON_HEADERS,
    )


def api_client(cfg: Config, jwt: str, *, allow_write: bool = False) -> httpx.Client:
    """Kimlikli MHRS API client'ı (`Authorization: Bearer <jwt>`).

    `allow_write=False` (varsayılan): yazma sınıfı bir uca gidilirse `WriteNotAllowed`.
    Randevu alma/iptal tool'ları açıkça `allow_write=True` geçer.

    MHRS `cfg.mhrs_min_interval` (varsayılan 2.0 s) ile throttle'lanır — e-Nabız'dan
    ayrı, çünkü RNDS1000 anti-bot kilidi burada gerçek bir risk ve throttle artık
    host'a göre keyli.
    """
    client = build_client(
        dataclasses.replace(cfg, base_url=API_BASE, min_interval=cfg.mhrs_min_interval),
        cookies=httpx.Cookies(),
        extra_headers={**_JSON_HEADERS, "Authorization": f"Bearer {jwt}"},
    )
    if not allow_write:
        client.event_hooks["request"].append(_forbid_write)
    return client


def unwrap(resp: httpx.Response) -> dict:
    """MHRS zarfını açar ve `data`'yı döndürür; hata kodlarını exception'a çevirir.

    Zarf: `{lang, success, infos[], warnings[], errors[], data}`. `success` HTTP
    durumundan BAĞIMSIZDIR — 200 ile hata dönebilir, o yüzden gövdeye bakılır.

    Reponun ilk JSON okuyucusu: 25+ parser'ın hepsi BeautifulSoup'tu.
    """
    from .auth import MhrsAuthRequired, MhrsError, MhrsRateLimited

    if resp.status_code in (401, 403):
        raise MhrsAuthRequired(f"MHRS oturumu reddedildi (HTTP {resp.status_code}).")
    try:
        body = resp.json()
    except ValueError as exc:
        raise MhrsError(f"MHRS JSON olmayan yanıt döndü (HTTP {resp.status_code}).") from exc
    if not isinstance(body, dict):
        raise MhrsError("MHRS beklenen zarfı döndürmedi.")

    if body.get("success"):
        data = body.get("data")
        return data if isinstance(data, dict) else {"data": data}

    errors = body.get("errors") or []
    first = errors[0] if errors and isinstance(errors[0], dict) else {}
    kodu = first.get("kodu")
    mesaj = first.get("mesaj") or "MHRS bilinmeyen hata."

    if kodu == "RNDS1000":
        # Retry ETME — kilidi derinleştirir ve kullanıcıyı online randevudan çıkarır.
        raise MhrsRateLimited(
            f"MHRS anti-bot kilidi (RNDS1000): {mesaj} "
            "Sorgu TEKRARLANMAYACAK — tekrar denemek kilidi derinleştirir.",
            kodu,
        )
    if kodu in {"LGN1004", "LGN2001"}:
        raise MhrsAuthRequired(f"MHRS oturumu geçersiz ({kodu}): {mesaj}", kodu)
    raise MhrsError(f"MHRS hatası ({kodu or '?'}): {mesaj}", kodu)


__all__ = [
    "API_BASE",
    "BUNDLE_ORIGIN",
    "ApiBoundaryViolation",
    "WriteNotAllowed",
    "anon_api_client",
    "api_client",
    "bundle_client",
    "unwrap",
]
