"""Hastane ziyareti (muayene) tool'ları (salt-okunur).

Liste: POST /Ziyaret/Index {baslangicYil, bitisYil} → kart ızgarası
(#ziyaretlerContainer > .ziyaretCardList). Ziyaret detayı (GetZiyaretDetay) ve
değerlendirme/paylaşım aksiyon uçları KULLANILMAZ — yalnız özet listelenir.
"""

from __future__ import annotations

import datetime

from fastmcp import FastMCP

from .. import auth
from .._text import tr_contains
from ..client import xhr_post
from ..config import Config
from ..parsers import parse_hospital_visits, parse_visit_detail
from ._common import apply_limit, auth_guarded

LIST_PATH = "/Ziyaret/Index"
PAGE = "/Home/Ziyaretlerim"
DETAIL_PATH = "/Ziyaret/GetZiyaretDetay"


def register(mcp: FastMCP) -> None:
    """Hastane ziyareti tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_hospital_visits(
        start_year: int | None = None,
        end_year: int | None = None,
        query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız hastane ziyaretlerini (muayeneler) yıl aralığına göre listeler.

        - `start_year` / `end_year`: yıl aralığı. Verilmezse son 6 takvim yılı
          (bu yıl - 5 … bu yıl; ziyaret sık
          bir alandır; daha eski kayıtlar için aralığı genişletin).
        - `query`: verilirse hastane/klinik alanında büyük/küçük harf duyarsız filtre.

        Her ziyaret tarih, hastane, klinik/branş, hekim ve takip no ile döner (özet).
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
            items = parse_hospital_visits(resp.text)

        if query:
            items = [
                v for v in items
                if tr_contains(query, v.hospital) or tr_contains(query, v.clinic)
            ]

        items, env = apply_limit(items, limit)
        return {
            "year_range": [start, end],
            **env,
            "visits": [v.model_dump() for v in items],
        }

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_get_visit_detail(detail_ref: str) -> dict:
        """Bir hastane ziyaretinin detayını döndürür (tanılar + işlemler).

        `detail_ref` = `enabiz_list_hospital_visits` çıktısındaki bir ziyaretin
        `detail_ref` alanı (opak referans). Sonuç `diagnoses` (tanı),
        `preliminary_diagnoses` (ön tanı), `additional_diagnoses` (ek tanı) ve
        `procedures` (işlemler) listeleriyle döner.
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            resp = client.get(f"{DETAIL_PATH}?{detail_ref}")
            html = resp.text
            if 'name="TCKimlikNo"' in html:
                raise auth.AuthRequired("Oturum düşmüş görünüyor.")
            detail = parse_visit_detail(html)

        return {"detail": detail}
