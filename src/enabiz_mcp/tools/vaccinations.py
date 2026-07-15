"""Aşı tool'ları (salt-okunur).

Liste: GET /Home/AsiTakvimi → sayfa-içi tablo #tblAsilar.
"""

from __future__ import annotations

from fastmcp import FastMCP

from .. import auth
from .._text import tr_contains
from ..config import Config
from ..parsers import parse_vaccinations
from ._common import apply_limit, auth_guarded

PAGE = "/Home/AsiTakvimi"


def register(mcp: FastMCP) -> None:
    """Aşı tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_vaccinations(
        query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız aşı takvimini listeler — salt-okunur.

        Her aşı işlem zamanı, aşı adı, doz ve yapılma yeri ile döner. `query`
        verilirse aşı adında büyük/küçük harf duyarsız filtre uygular.
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.

        - `limit`: en fazla kaç kayıt döner (varsayılan 50; `0` = sınırsız).
          `truncated: true` ise liste kırpılmıştır.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            html = client.get(PAGE).text
            if 'name="TCKimlikNo"' in html:
                raise auth.AuthRequired("Oturum düşmüş görünüyor.")
            items = parse_vaccinations(html)

        if query:
            items = [v for v in items if tr_contains(query, v.vaccine)]

        items, env = apply_limit(items, limit)
        return {
            **env,
            "vaccinations": [v.model_dump() for v in items],
        }
