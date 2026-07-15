"""İdari alan tool'ları (salt-okunur): sigorta, malzeme/cihaz, acil durum notları.

Hepsi sunucu-render GET-sayfa tabloları. Aksiyon/paylaşım endpoint'leri KULLANILMAZ.
"""

from __future__ import annotations

from fastmcp import FastMCP

from .. import auth
from .._text import tr_contains
from ..config import Config
from ..parsers import parse_emergency_notes, parse_insurance, parse_materials_devices
from ._common import apply_limit, auth_guarded

SIGORTA_PAGE = "/Home/Sigortalarim"
MALZEME_PAGE = "/Home/MalzemeveCihazlarim"
ACIL_PAGE = "/Home/AcilDurumNotlarim"


def _get(page: str) -> str:
    """Kimlikli GET; oturum düşmüşse AuthRequired."""
    cfg = Config.from_env()
    with auth.session_scope(cfg) as client:
        html = client.get(page).text
    if 'name="TCKimlikNo"' in html:
        raise auth.AuthRequired("Oturum düşmüş görünüyor.")
    return html


def register(mcp: FastMCP) -> None:
    """İdari tool'ları verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_insurance(
        query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız sigorta kayıtlarını listeler — salt-okunur.

        Her kayıt açıklama, sigorta kodu, tarih aralığı, ek süre ve durum ile döner.
        `query` verilirse açıklamada büyük/küçük harf duyarsız filtre uygular.
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.

        - `limit`: en fazla kaç kayıt döner (varsayılan 50; `0` = sınırsız).
          `truncated: true` ise liste kırpılmıştır.
        """
        items = parse_insurance(_get(SIGORTA_PAGE))
        if query:
            items = [i for i in items if tr_contains(query, i.description)]
        items, env = apply_limit(items, limit)
        return {**env, "insurance": [i.model_dump() for i in items]}

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_materials_devices(
        category: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız tıbbi malzeme/cihaz kayıtlarını listeler — salt-okunur.

        5 kategoriyi birleştirir: `diger`, `vucut`, `isitme`, `goz`, `ozel_yapim`.
        Her kayıt işlem tarihi, marka, raf ömrü, ürün tanımı ve kategori ile döner.
        `category` verilirse yalnız o kategori döner. Kimlikli oturum gerektirir.

        - `limit`: en fazla kaç kayıt döner (varsayılan 50; `0` = sınırsız).
          `truncated: true` ise liste kırpılmıştır.
        """
        items = parse_materials_devices(_get(MALZEME_PAGE))
        if category:
            c = category.lower()
            items = [m for m in items if m.category == c]
        items, env = apply_limit(items, limit)
        return {**env, "materials_devices": [m.model_dump() for m in items]}

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_emergency_notes(
        query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız acil durum notlarını listeler — salt-okunur.

        Her not tarih, konu ve açıklama ile döner. `query` verilirse konuda
        büyük/küçük harf duyarsız filtre uygular. Kimlikli oturum gerektirir.

        - `limit`: en fazla kaç kayıt döner (varsayılan 50; `0` = sınırsız).
          `truncated: true` ise liste kırpılmıştır.
        """
        items = parse_emergency_notes(_get(ACIL_PAGE))
        if query:
            items = [n for n in items if tr_contains(query, n.subject)]
        items, env = apply_limit(items, limit)
        return {**env, "emergency_notes": [n.model_dump() for n in items]}
