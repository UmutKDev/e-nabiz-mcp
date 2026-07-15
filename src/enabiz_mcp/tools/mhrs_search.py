"""MHRS lookup tool'ları — il / ilçe / klinik (salt-okunur).

Randevu aramanın ön adımları: MHRS her şeyi id ile ister (`mhrsIlId`, `mhrsKlinikId`),
ad ile değil. Bu tool'lar o id'leri bulmayı sağlar; hiçbiri kullanıcıya ait veri
döndürmez — il ve klinik listeleri herkeste aynıdır.

**Yanıt şekli uca göre değişir** (`mhrs/client.py::unwrap`): buradaki üç uçtan
il ve ilçe ÇIPLAK DİZİ döner, klinik ZARFLI döner. Prefix'ten tahmin edilemez.

Ağaç yapısı: il/klinik uçları `children[]` ile iki seviyeli gelir (ör. il → ilçe
kırılımı). Düzleştirmiyoruz — `children` olduğu gibi taşınır ki model hiyerarşiyi
görebilsin.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..config import Config
from ..mhrs.auth import mhrs_session
from ..mhrs.client import api_client, unwrap
from ._common import auth_guarded

IL_PATH = "yonetim/genel/il/selectinput-tree"
ILCE_PATH = "yonetim/genel/ilce/selectinput/{il_id}"
KLINIK_PATH = "kurum/kurum/kurum-klinik/klinik/select-input"

#: MHRS'nin "farketmez / hepsi" sentinel'i. Bundle bunu her boş form alanı için
#: gönderiyor; tool'larda da aynı anlamı taşır.
ANY_ID = "-1"


def _node(raw: Any) -> dict | None:
    """Bir selectinput düğümünü sözleşme alanlarına indirger.

    Her değer `str`/`str | None` kalır — ev kuralı (`CLAUDE.md`): `value` bir id
    gibi görünse de int'e ÇEVRİLMEZ. MHRS `-1` sentinel'i, `"0"` ve gerçek id'leri
    aynı alanda taşıyor; sayıya çevirmek `0`ı falsy yapıp sentinel mantığını bozan
    tam da MHRS'nin kendi bundle'ında düzeltmek zorunda kaldığı hatadır
    (`mhrsHekimId: 0 !== e.mhrsHekimId ? ... : -1`).

    `value2`/`value3` bundle'da `favori` ve `cetvelTipi` olarak parse ediliyor
    (`j()` dönüştürücüsü, vatandas-45-chunk.js) — anlamlı adlarıyla taşınır.
    """
    if not isinstance(raw, dict):
        return None
    text = raw.get("text")
    value = raw.get("value")
    if text is None and value is None:
        return None
    out: dict = {
        "id": None if value is None else str(value),
        "name": None if text is None else str(text),
    }
    if raw.get("value2") is not None:
        out["favori_kodu"] = str(raw["value2"])
    if raw.get("value3") is not None:
        out["cetvel_tipi"] = str(raw["value3"])
    children = [c for c in (_node(c) for c in raw.get("children") or []) if c]
    if children:
        out["children"] = children
    return out


def _nodes(raw: Any) -> list[dict]:
    """Liste yanıtını düğümlere çevirir; beklenmeyen şekilde `[]` döner.

    Sessiz yanlış-eşleme yerine boş sonuç (invaryant #2): MHRS beklenmedik bir şey
    döndürürse uydurma bir liste değil, hiçbir şey.
    """
    if not isinstance(raw, list):
        return []
    return [n for n in (_node(x) for x in raw) if n]


def register(mcp: FastMCP) -> None:
    """MHRS lookup tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_list_provinces() -> dict:
        """MHRS il listesini döndürür — salt-okunur.

        Randevu aramanın ilk adımı: MHRS il/ilçe/klinik'i id ile ister, ad ile değil.
        Her il `id` ve `name` taşır; bazı iller `children` ile ilçe kırılımı içerir.
        Bu liste kullanıcıya özel DEĞİLDİR.

        E-Nabız oturumu gerektirir (MHRS oturumu SSO ile otomatik alınır).
        """
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        with api_client(cfg, session.jwt) as client:
            data = unwrap(client.get(IL_PATH))
        items = _nodes(data)
        return {"count": len(items), "provinces": items}

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_list_districts(province_id: str) -> dict:
        """Bir ilin ilçelerini döndürür — salt-okunur.

        - `province_id`: `enabiz_mhrs_list_provinces`'ten gelen `id`.

        MHRS ilçe listesini ÇIPLAK dizi olarak döner (zarfsız) — il listesinden
        farklı olarak `children` içermez.
        """
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        with api_client(cfg, session.jwt) as client:
            data = unwrap(client.get(ILCE_PATH.format(il_id=province_id)))
        items = _nodes(data)
        return {"count": len(items), "province_id": province_id, "districts": items}

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_list_clinics() -> dict:
        """MHRS klinik (branş) listesini döndürür — salt-okunur.

        Ağaç yapısındadır: üst düğümler branş grubu, `children` alt branşlar.
        Randevu ararken `id` gerekir. Bu liste kullanıcıya özel DEĞİLDİR.
        """
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        with api_client(cfg, session.jwt) as client:
            data = unwrap(client.get(KLINIK_PATH))
        items = _nodes(data)
        return {"count": len(items), "clinics": items}
