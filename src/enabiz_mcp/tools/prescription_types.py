"""Optik ve tıbbi cihaz reçete tool'ları (salt-okunur).

İlaç reçeteleri `prescriptions.py`'de; bunlar ayrı reçete türleridir:
  - Optik:  POST /Recete/GetOptikReceteler {baslangicYil,bitisYil} → #tbl-optikRecetelerim
  - Cihaz:  POST /Recete/GetTibbiCihazReceteler {baslangicYil,bitisYil} → #tbl-tibbiCihazRecetelerim
Token/referer sayfası: /Home/Recetelerim.
"""

from __future__ import annotations

import datetime

from fastmcp import FastMCP

from .. import auth
from .._text import tr_contains
from ..client import xhr_post
from ..config import Config
from ..parsers import parse_device_prescriptions, parse_optical_prescriptions
from ._common import apply_limit, auth_guarded

PAGE = "/Home/Recetelerim"
OPTIK_PATH = "/Recete/GetOptikReceteler"
CIHAZ_PATH = "/Recete/GetTibbiCihazReceteler"


def register(mcp: FastMCP) -> None:
    """Optik/cihaz reçete tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_optical_prescriptions(
        start_year: int | None = None,
        end_year: int | None = None,
        type_query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız optik (gözlük/lens) reçetelerini yıl aralığına göre listeler.

        - `start_year` / `end_year`: yıl aralığı. Verilmezse son 6 takvim yılı
          (bu yıl - 5 … bu yıl).
        - `type_query`: verilirse reçete TÜRÜNDE büyük/küçük harf duyarsız filtre.

        Her reçete tarih, reçete no, tür ve hekim ile döner.
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.

        - `limit`: en fazla kaç kayıt döner (varsayılan 50; `0` = sınırsız).
          `truncated: true` ise liste kırpılmıştır.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            token = auth.scrape_token(client, PAGE)
            this_year = datetime.date.today().year
            end = end_year or this_year
            start = start_year or (this_year - 5)
            resp = xhr_post(
                client,
                OPTIK_PATH,
                token,
                {"baslangicYil": str(start), "bitisYil": str(end)},
                referer=PAGE,
            )
            items = parse_optical_prescriptions(resp.text)

        if type_query:
            items = [o for o in items if tr_contains(type_query, o.type)]

        items, env = apply_limit(items, limit)
        return {
            "year_range": [start, end],
            **env,
            "optical_prescriptions": [o.model_dump() for o in items],
        }

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_device_prescriptions(
        start_year: int | None = None,
        end_year: int | None = None,
        facility_query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız tıbbi cihaz reçetelerini yıl aralığına göre listeler.

        - `start_year` / `end_year`: yıl aralığı. Verilmezse son 6 takvim yılı
          (bu yıl - 5 … bu yıl).
        - `facility_query`: verilirse TESİS bilgisinde büyük/küçük harf duyarsız filtre.

        Her reçete tarih, reçete no, hekim ve tesis bilgisi ile döner.
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.

        - `limit`: en fazla kaç kayıt döner (varsayılan 50; `0` = sınırsız).
          `truncated: true` ise liste kırpılmıştır.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            token = auth.scrape_token(client, PAGE)
            this_year = datetime.date.today().year
            end = end_year or this_year
            start = start_year or (this_year - 5)
            resp = xhr_post(
                client,
                CIHAZ_PATH,
                token,
                {"baslangicYil": str(start), "bitisYil": str(end)},
                referer=PAGE,
            )
            items = parse_device_prescriptions(resp.text)

        if facility_query:
            items = [c for c in items if tr_contains(facility_query, c.facility)]

        items, env = apply_limit(items, limit)
        return {
            "year_range": [start, end],
            **env,
            "device_prescriptions": [c.model_dump() for c in items],
        }
