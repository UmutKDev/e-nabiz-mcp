"""Randevu tool'ları (salt-okunur).

Liste: GET /Home/Randevularim → sayfa-içi tablo #tblRandevuListesi.
DİKKAT: `/Randevu/*` aksiyon endpoint'leri (RandevuAl, RandevuIptal, ...) BU
tool'lar tarafından KULLANILMAZ — yalnızca mevcut randevular listelenir.
"""

from __future__ import annotations

from fastmcp import FastMCP

from .. import auth
from .._text import tr_contains
from ..config import Config
from ..parsers import parse_appointments
from ._common import apply_limit, auth_guarded

PAGE = "/Home/Randevularim"


def register(mcp: FastMCP) -> None:
    """Randevu tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_appointments(
        status_query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız (MHRS) randevularını listeler — salt-okunur.

        Sayfada gösterilen randevuları döndürür (tarih/saat, kurum, klinik, muayene
        yeri, hekim, durum, tür). `status_query` verilirse durum alanında büyük/küçük
        harf duyarsız filtre uygular. Randevu **almaz/iptal etmez**. Kimlikli oturum
        gerektirir; yoksa `error: "auth_required"`.

        - `limit`: en fazla kaç kayıt döner (varsayılan 50; `0` = sınırsız).
          `truncated: true` ise liste kırpılmıştır.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            html = client.get(PAGE).text
            if 'name="TCKimlikNo"' in html:
                raise auth.AuthRequired("Oturum düşmüş görünüyor.")
            items = parse_appointments(html)

        if status_query:
            items = [a for a in items if tr_contains(status_query, a.status)]

        items, env = apply_limit(items, limit)
        return {
            **env,
            "appointments": [a.model_dump() for a in items],
        }
