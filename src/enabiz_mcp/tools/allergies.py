"""Alerji tool'ları (salt-okunur).

Liste: GET /Home/Alerjilerim → sayfa-içi 3 tablo (ilaç / tanı-bazlı / deri testi).
Aksiyon endpoint'leri (AlerjiEkle/Sil/Duzenle) KULLANILMAZ.
"""

from __future__ import annotations

from fastmcp import FastMCP

from .. import auth
from ..config import Config
from ..parsers import parse_allergies
from ._common import apply_limit, auth_guarded

PAGE = "/Home/Alerjilerim"


def register(mcp: FastMCP) -> None:
    """Alerji tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_allergies(
        category: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız alerji kayıtlarını listeler — salt-okunur.

        Üç kategoriyi birleştirir: `ilac` (ilaç alerjileri), `tani` (tanı bazlı),
        `deri` (deri/prick testleri). Her kayıt tarih, kategori, alerji türü, ilaç
        adı ve belirtileri ile döner. `category` verilirse yalnız o kategori döner.
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.

        - `limit`: en fazla kaç kayıt döner (varsayılan 50; `0` = sınırsız).
          `truncated: true` ise liste kırpılmıştır.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            html = client.get(PAGE).text
            if 'name="TCKimlikNo"' in html:
                raise auth.AuthRequired("Oturum düşmüş görünüyor.")
            items = parse_allergies(html)

        if category:
            q = category.lower()
            items = [a for a in items if a.category == q]

        items, env = apply_limit(items, limit)
        return {
            **env,
            "allergies": [a.model_dump() for a in items],
        }
