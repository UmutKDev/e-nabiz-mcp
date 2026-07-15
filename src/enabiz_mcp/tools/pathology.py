"""Patoloji tool'ları (salt-okunur).

Liste: POST /Patoloji/Index {baslangicYili, bitisYili} → HTML tablo #tblPatoloji.
⚠ Yıl param adları epikrizden FARKLI (`...Yili`, sonu "i"). PDF detayı
(PDFGetir → /Patoloji/GetPatolojiPdf) Faz 4'te; liste `sys_no`'yu taşır.
"""

from __future__ import annotations

import datetime

from fastmcp import FastMCP

from .. import auth
from .._text import tr_contains
from ..client import xhr_post
from ..config import Config
from ..parsers import parse_pathology
from ._common import apply_limit, auth_guarded

LIST_PATH = "/Patoloji/Index"
PAGE = "/Home/Patolojilerim"


def register(mcp: FastMCP) -> None:
    """Patoloji tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_pathology(
        start_year: int | None = None,
        end_year: int | None = None,
        query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız patoloji kayıtlarını yıl aralığına göre listeler.

        - `start_year` / `end_year`: yıl aralığı. Verilmezse son 11 takvim yılı
          (bu yıl - 10 … bu yıl; patoloji
          seyrek, ömür-boyu kayıtlardır → geniş varsayılan).
        - `query`: verilirse hastane/klinik alanında büyük/küçük harf duyarsız filtre.

        Her kayıt tarih, referans no, hastane, klinik, hekim ve PDF için `sys_no`
        ile döner. Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.

        - `limit`: en fazla kaç kayıt döner (varsayılan 50; `0` = sınırsız).
          `truncated: true` ise liste kırpılmıştır.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            token = auth.scrape_token(client, PAGE)
            this_year = datetime.date.today().year
            end = end_year or this_year
            start = start_year or (this_year - 10)
            resp = xhr_post(
                client,
                LIST_PATH,
                token,
                {"baslangicYili": str(start), "bitisYili": str(end)},
                referer=PAGE,
            )
            items = parse_pathology(resp.text)

        if query:
            items = [
                p for p in items
                if tr_contains(query, p.hospital) or tr_contains(query, p.clinic)
            ]

        items, env = apply_limit(items, limit)
        return {
            "year_range": [start, end],
            **env,
            "pathology": [p.model_dump() for p in items],
        }

