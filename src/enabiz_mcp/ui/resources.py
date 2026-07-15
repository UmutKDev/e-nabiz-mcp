"""Widget HTML'lerini `ui://` kaynağı olarak kaydeder.

Kaynaklar protokol üzerinden (`resources/read`) servis edilir — HTTP sunucusu
YOK. Bu, D3'ün (stdio-only, uzak transport yok) ihlali değil: widget HTML'i
istemciye MCP kanalından, aynı stdio borusundan gider.
"""

from __future__ import annotations

import functools
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP

from .bundle import inline_bundle
from .schema import TABLE_URI

_WIDGETS = Path(__file__).parent / "widgets"

#: Widget hiçbir yere bağlanamaz, hiçbir dış kaynak yükleyemez.
#: Boş liste bir ihmal DEĞİL, açık beyandır: privacy.md §1-2 uyarınca bu
#: konteynerde tek meşru egress sunucunun kendi enabiz.gov.tr çağrılarıdır —
#: iframe'in kendi başına dışarı konuşması hiçbir senaryoda meşru değil.
_NO_EGRESS = ResourceCSP(connect_domains=[], resource_domains=[], frame_domains=[])


@functools.cache
def _widget(name: str) -> str:
    """Widget HTML'ini okur ve ext-apps paketini gömer (süreç başına bir kez)."""
    return inline_bundle((_WIDGETS / name).read_text(encoding="utf-8"))


def register(mcp: FastMCP) -> None:
    """Widget kaynaklarını verilen FastMCP örneğine kaydeder."""

    # mime otomatik `text/html;profile=mcp-app` olur (ui:// şeması) —
    # host'un bunu iframe olarak render etmesini sağlayan tek sinyal budur.
    @mcp.resource(TABLE_URI, app=AppConfig(csp=_NO_EGRESS))
    def table_widget() -> str:
        """Zaman omurgalı jenerik kayıt tablosu."""
        return _widget("table.html")
