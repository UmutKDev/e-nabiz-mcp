"""Kronik hastalık takip tool'ları (salt-okunur).

Liste: GET /Home/HastalikTakip → sayfa-içi tablo #tblHastalikTakip.
"""

from __future__ import annotations

from fastmcp import FastMCP

from .. import auth
from .._text import tr_contains
from ..config import Config
from ..parsers import parse_chronic_followups
from ._common import apply_limit, auth_guarded

PAGE = "/Home/HastalikTakip"


def register(mcp: FastMCP) -> None:
    """Kronik takip tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_chronic_disease_followups(
        query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız kronik hastalık takip kayıtlarını listeler — salt-okunur.

        Her kayıt takip tipi, kronik hastalık, takip tarihi, planlanan tarih ve
        gerçekleşme durumu ile döner. `query` verilirse kronik hastalık alanında
        büyük/küçük harf duyarsız filtre uygular. Bu, tanı geçmişinden (Hastaliklarim)
        AYRI bir alandır. Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.

        - `limit`: en fazla kaç kayıt döner (varsayılan 50; `0` = sınırsız).
          `truncated: true` ise liste kırpılmıştır.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            html = client.get(PAGE).text
            if 'name="TCKimlikNo"' in html:
                raise auth.AuthRequired("Oturum düşmüş görünüyor.")
            items = parse_chronic_followups(html)

        if query:
            items = [c for c in items if tr_contains(query, c.chronic_disease)]

        items, env = apply_limit(items, limit)
        return {
            **env,
            "followups": [c.model_dump() for c in items],
        }
