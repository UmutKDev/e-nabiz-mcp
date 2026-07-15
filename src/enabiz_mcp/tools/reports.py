"""Sağlık raporu tool'ları.

Liste: POST /Rapor/Index {startYear, endYear} → HTML tablo (#tblRaporlarim).
Not: bu endpoint yıl parametrelerini `startYear`/`endYear` olarak ister
(reçetedeki `baslangicYil` ve tahlildeki `baslangicTarihi`'den farklı).
"""

from __future__ import annotations

import datetime

from fastmcp import FastMCP

from .. import auth
from .._text import tr_contains
from ..client import xhr_post
from ..config import Config
from ..parsers import parse_reports
from ._common import apply_limit, auth_guarded

LIST_PATH = "/Rapor/Index"
PAGE = "/Home/Raporlarim"


def register(mcp: FastMCP) -> None:
    """Rapor tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_reports(
        start_year: int | None = None,
        end_year: int | None = None,
        type_query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız sağlık raporlarını yıl aralığına göre listeler.

        - `start_year` / `end_year`: yıl aralığı. Verilmezse son 6 takvim yılı
          (bu yıl - 5 … bu yıl).
        - `type_query`: verilirse rapor türünde büyük/küçük harf duyarsız filtre.

        Her rapor tarih, no, takip no, tür, geçerlilik aralığı ve tanı ile döner.
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
                LIST_PATH,
                token,
                {"startYear": str(start), "endYear": str(end)},
                referer=PAGE,
            )
            items = parse_reports(resp.text)

        if type_query:
            items = [r for r in items if tr_contains(type_query, r.type)]

        items, env = apply_limit(items, limit)
        return {
            "year_range": [start, end],
            **env,
            "reports": [r.model_dump() for r in items],
        }
