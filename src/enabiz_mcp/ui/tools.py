"""Widget'ın çağırdığı arka-uç tool'u — `visibility: ["app"]`.

Bu tool modelin tool listesinde GÖRÜNMEZ; yalnız widget `app.callServerTool()`
ile çağırır ve yanıt widget'a gider, modelin bağlamına değil. İnvaryant #3'ü
(PHI, LLM bağlamına girmez) liste alanlarında uygulayan mekanizma budur.
"""

from __future__ import annotations

import inspect
import json
from typing import Any

from fastmcp import FastMCP
from fastmcp.apps import AppConfig

from ..tools._common import auth_guarded
from . import registry

#: Host payload tavanı ~150k karakter; aşılırsa host yanıtı bir dosya-işaretçisi
#: dizesiyle DEĞİŞTİRİR ve widget'taki `JSON.parse` boyut ipucu olmadan patlar.
#: Kendimizi güvenli tarafta keseriz.
#:
#: Bu, metin yolundaki `DEFAULT_LIMIT`ten AYRI bir sınırdır ve gerekçesi farklı:
#: `DEFAULT_LIMIT` modelin BAĞLAMINI korur (token maliyeti), bu ise host'un
#: TAŞIMA tavanını korur. Widget'a giden veri modele gitmediği için token kaygısı
#: yoktur — bu yüzden burada `apply_limit` KULLANILMAZ.
MAX_PAYLOAD_CHARS = 130_000


def _fit(rows: list[dict], base: dict) -> tuple[list[dict], bool]:
    """Satırları payload tavanına sığdırır; `(satırlar, kırpıldı_mı)` döner.

    Kolon budamak yerine satır kırpar: kolonlar şemadan gelir ve eksik kolon
    SESSİZCE yanlış bir tablo üretir (invaryant #2). Eksik satır ise görünür
    ve `truncated` ile beyan edilir.
    """
    if len(json.dumps({**base, "rows": rows}, ensure_ascii=False)) <= MAX_PAYLOAD_CHARS:
        return rows, False

    lo, hi = 0, len(rows)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        probe = json.dumps({**base, "rows": rows[:mid]}, ensure_ascii=False)
        if len(probe) <= MAX_PAYLOAD_CHARS:
            lo = mid
        else:
            hi = mid - 1
    return rows[:lo], True


def register(mcp: FastMCP) -> None:
    """Widget arka-uç tool'unu verilen FastMCP örneğine kaydeder."""

    @mcp.tool(
        app=AppConfig(visibility=["app"]),
        annotations={"readOnlyHint": True, "openWorldHint": True},
    )
    @auth_guarded
    def enabiz_ui_data(domain: str, params: dict[str, Any] | None = None) -> dict:
        """Panel için kayıtları getirir — yalnız panelin çağırdığı iç uç.

        Bu tool'u model çağırmaz; kullanıcının gördüğü panel çağırır. Model
        tarafındaki karşılığı `enabiz_list_*` tool'larıdır.
        """
        dom = registry.get(domain)
        if dom is None:
            return {
                "error": "unknown_domain",
                "message": f"Bilinmeyen veri alanı: {domain!r}",
                "known": sorted(registry.DOMAINS),
            }

        args = dict(params or {})
        kabul = set(inspect.signature(dom.fetch).parameters)
        # Bilinmeyen parametre SESSİZCE düşürülmez: düşürürsek widget filtreli
        # sandığı listeyi filtresiz gösterir — sessiz yanlış-eşleme (invaryant #2).
        if fazla := set(args) - kabul:
            return {
                "error": "unknown_params",
                "message": f"{domain} bu parametreleri tanımıyor: {sorted(fazla)}",
                "known": sorted(kabul),
            }

        items = dom.fetch(**args)
        sch = dom.schema
        base = {
            "domain": domain,
            "title": sch.title,
            "columns": [
                {"key": c.key, "label": c.label, "role": c.role, "values": c.values}
                for c in sch.columns
            ],
            "empty_text": sch.empty_text,
        }
        rows, kirpildi = _fit([i.model_dump() for i in items], base)
        return {
            **base,
            "rows": rows,
            "count": len(rows),
            "total": len(items),
            "truncated": kirpildi,
        }
