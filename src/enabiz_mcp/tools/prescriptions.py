"""Reçete tool'ları.

Liste: POST /Recete/Index {baslangicYil, bitisYil} → HTML tablo (#tbl-recetelerim).
Detay: POST /Recete/GetReceteDetay?data={"SYSTakipNo":..,"ReceteNo":..} → ilaç HTML'i.
"""

from __future__ import annotations

import datetime
import json

from fastmcp import FastMCP

from .. import auth
from .._text import tr_contains
from ..client import xhr_post
from ..config import Config
from ..parsers import parse_prescription_detail, parse_prescriptions
from ._common import apply_limit, auth_guarded

LIST_PATH = "/Recete/Index"
DETAIL_PATH = "/Recete/GetReceteDetay"
PAGE = "/Home/Recetelerim"


def register(mcp: FastMCP) -> None:
    """Reçete tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_prescriptions(
        start_year: int | None = None,
        end_year: int | None = None,
        doctor_query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız reçetelerini yıl aralığına göre listeler.

        - `start_year` / `end_year`: yıl aralığı. Verilmezse son 6 takvim yılı
          (bu yıl - 5 … bu yıl).
        - `doctor_query`: verilirse hekim adında büyük/küçük harf duyarsız filtre.

        Her reçete metadatası döner (tarih, no, tür, hekim). İlaç ayrıntısı için
        `enabiz_get_prescription_detail`'i `sys_takip_no` + `prescription_no` ile çağırın.
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.

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
            items = parse_prescriptions(resp.text)

        if doctor_query:
            items = [p for p in items if tr_contains(doctor_query, p.doctor)]

        items, env = apply_limit(items, limit)
        return {
            "year_range": [start, end],
            **env,
            "prescriptions": [p.model_dump() for p in items],
        }

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_get_prescription_detail(sys_takip_no: str, prescription_no: str) -> dict:
        """Bir reçetenin ilaç ayrıntısını döndürür.

        `sys_takip_no` ve `prescription_no` değerleri `enabiz_list_prescriptions`
        çıktısındaki ilgili reçeteden alınır. Kimlikli oturum gerektirir.
        """
        cfg = Config.from_env()
        veri = json.dumps({"SYSTakipNo": sys_takip_no, "ReceteNo": prescription_no})
        with auth.session_scope(cfg) as client:
            token = auth.scrape_token(client, PAGE)
            resp = xhr_post(
                client,
                f"{DETAIL_PATH}?data={veri}",
                token,
                {},
                referer=PAGE,
            )
            drugs = parse_prescription_detail(resp.text)

        return {
            "sys_takip_no": sys_takip_no,
            "prescription_no": prescription_no,
            "drug_count": len(drugs),
            "drugs": drugs,
        }
