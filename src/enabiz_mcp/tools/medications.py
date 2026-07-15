"""İlaç tool'ları.

Liste: POST /Ilac/Index {baslangicYil, bitisYil} → HTML tablo (#tblIlaclarim).
Reçete bazlı düz ilaç kaydı (hastane/klinik bağlamıyla).
"""

from __future__ import annotations

import datetime

from fastmcp import FastMCP

from .. import auth
from .._text import tr_contains
from ..client import xhr_post
from ..config import Config
from ..parsers import html_to_text, parse_drug_usage_history, parse_medications
from ._common import apply_limit, auth_guarded

LIST_PATH = "/Ilac/Index"
PAGE = "/Home/Ilaclarim"
RECETE_PAGE = "/Home/Recetelerim"  # /Recete/* uçları için token/referer sayfası
LEAFLET_PATH = "/Recete/GetIlacProspektusBilgisi"
USAGE_HISTORY_PATH = "/Recete/GetIlacKullanimGecmisi"
LEAFLET_TEXT_LIMIT = 20_000


def register(mcp: FastMCP) -> None:
    """İlaç tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_medications(
        start_year: int | None = None,
        end_year: int | None = None,
        drug_query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız kullanılan ilaçları yıl aralığına göre listeler.

        - `start_year` / `end_year`: yıl aralığı. Verilmezse son 6 takvim yılı
          (bu yıl - 5 … bu yıl).
        - `drug_query`: verilirse ilaç adında büyük/küçük harf duyarsız filtre.

        Her ilaç reçete tarihi, barkod, ad, doz, periyot, kullanım, kutu adedi,
        hastane ve klinik ile döner. Kimlikli oturum gerektirir; yoksa
        `error: "auth_required"`.

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
                {"baslangicYil": str(start), "bitisYil": str(end)},
                referer=PAGE,
            )
            items = parse_medications(resp.text)

        if drug_query:
            items = [m for m in items if tr_contains(drug_query, m.name)]

        items, env = apply_limit(items, limit)
        return {
            "year_range": [start, end],
            **env,
            "medications": [m.model_dump() for m in items],
        }

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_get_drug_leaflet(barcode: str, ilac_name: str) -> dict:
        """Bir ilacın prospektüs (kullanma talimatı) metnini döndürür.

        `barcode` ve `ilac_name`, `enabiz_list_medications` çıktısındaki bir ilacın
        `barcode` / `name` alanlarından alınır. Prospektüs serbest metin olarak döner
        (uzunsa `LEAFLET_TEXT_LIMIT`'te kırpılır).
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            token = auth.scrape_token(client, RECETE_PAGE)
            resp = xhr_post(
                client,
                LEAFLET_PATH,
                token,
                {"barcode": barcode, "ilacName": ilac_name},
                referer=RECETE_PAGE,
            )
            text = html_to_text(resp.text)

        return {
            "barcode": barcode,
            "ilac_name": ilac_name,
            "leaflet_text": text[:LEAFLET_TEXT_LIMIT],
            "truncated": len(text) > LEAFLET_TEXT_LIMIT,
        }

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_get_drug_usage_history(barcode: str) -> dict:
        """Bir ilacın (barkod) kullanım geçmişini döndürür.

        `barcode`, `enabiz_list_medications` çıktısındaki bir ilacın `barcode` alanından
        alınır. Her kayıt tarih, ilaç adı/açıklaması, doz, kullanım sayısı, periyot ve
        kullanım şekli ile döner. Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            token = auth.scrape_token(client, RECETE_PAGE)
            resp = xhr_post(
                client,
                USAGE_HISTORY_PATH,
                token,
                {"barcode": barcode},
                referer=RECETE_PAGE,
            )
            items = parse_drug_usage_history(resp.text)

        return {
            "barcode": barcode,
            "count": len(items),
            "usage": [u.model_dump() for u in items],
        }
