"""Epikriz (taburcu özeti) tool'ları (salt-okunur).

Liste: POST /Epikriz/Index {baslangicYil, bitisYil} → HTML tablo #tblEpikriz.
Not: PDF detayı (PDFGetir → /Epikriz/GetEpikrizPdf) Faz 4'te ayrı bir tool olacak;
liste `sys_no` + `reference_no`'yu o çağrı için taşır.
"""

from __future__ import annotations

import datetime

from fastmcp import FastMCP

from .. import auth
from .._text import tr_contains
from ..client import xhr_post
from ..config import Config
from ..parsers import parse_discharge_summaries
from ._common import apply_limit, auth_guarded

LIST_PATH = "/Epikriz/Index"
PAGE = "/Home/Epikrizlerim"


def register(mcp: FastMCP) -> None:
    """Epikriz tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_discharge_summaries(
        start_year: int | None = None,
        end_year: int | None = None,
        query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız epikrizlerini (taburcu özetleri) yıl aralığına göre listeler.

        - `start_year` / `end_year`: yıl aralığı. Verilmezse son 11 takvim yılı
          (bu yıl - 10 … bu yıl; epikrizler
          ömür-boyu, seyrek kayıtlardır → geniş varsayılan).
        - `query`: verilirse hastane/klinik alanında büyük/küçük harf duyarsız filtre.

        Her epikriz tarih, referans no, hastane, klinik, hekim ve PDF için `sys_no`
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
                {"baslangicYil": str(start), "bitisYil": str(end)},
                referer=PAGE,
            )
            items = parse_discharge_summaries(resp.text)

        if query:
            items = [
                e for e in items
                if tr_contains(query, e.hospital) or tr_contains(query, e.clinic)
            ]

        items, env = apply_limit(items, limit)
        return {
            "year_range": [start, end],
            **env,
            "discharge_summaries": [e.model_dump() for e in items],
        }

