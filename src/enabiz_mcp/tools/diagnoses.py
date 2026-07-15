"""Tanı/hastalık tool'ları (salt-okunur).

Liste: GET /Home/Hastaliklarim → sayfa-içi tablo #tblHastaliklarim.
Detay: GET /hastalik/GetHastalikDetay?SysTakipNo=<token> → HTML (düz metne indirgenir).
"""

from __future__ import annotations

from fastmcp import FastMCP

from .. import auth
from .._text import tr_contains
from ..config import Config
from ..parsers import html_to_text, parse_diagnoses
from ._common import apply_limit, auth_guarded

PAGE = "/Home/Hastaliklarim"
DETAIL_PATH = "/hastalik/GetHastalikDetay"
DETAIL_TEXT_LIMIT = 20_000


def register(mcp: FastMCP) -> None:
    """Tanı tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_diagnoses(
        query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız tanı/hastalık geçmişini listeler — salt-okunur.

        Her tanı tarih, tanı (ICD kodu + ad), klinik, hekim ve detay için
        `sys_takip_no` ile döner. `query` verilirse tanı metninde büyük/küçük harf
        duyarsız filtre uygular. Detay için `enabiz_get_diagnosis_detail` kullanın.
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.

        - `limit`: en fazla kaç kayıt döner (varsayılan 50; `0` = sınırsız).
          `truncated: true` ise liste kırpılmıştır.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            html = client.get(PAGE).text
            if 'name="TCKimlikNo"' in html:
                raise auth.AuthRequired("Oturum düşmüş görünüyor.")
            items = parse_diagnoses(html)

        if query:
            items = [d for d in items if tr_contains(query, d.diagnosis)]

        items, env = apply_limit(items, limit)
        return {
            **env,
            "diagnoses": [d.model_dump() for d in items],
        }

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_get_diagnosis_detail(sys_takip_no: str) -> dict:
        """Bir tanının detay metnini döndürür (`sys_takip_no` = liste tool'undan).

        `enabiz_list_diagnoses` çıktısındaki `sys_takip_no` ile çağrılır. Detay HTML'i
        okunabilir düz metne indirgenir (uzunsa `DETAIL_TEXT_LIMIT`'te kırpılır).
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            resp = client.get(
                DETAIL_PATH,
                params={
                    "tarih": "",
                    "tani": "",
                    "ektani": "",
                    "ontani": "",
                    "ayiricitani": "",
                    "nadirhastaliktani": "",
                    "SysTakipNo": sys_takip_no,
                },
            )
            html = resp.text
            if 'name="TCKimlikNo"' in html:
                raise auth.AuthRequired("Oturum düşmüş görünüyor.")
            text = html_to_text(html)

        return {
            "sys_takip_no": sys_takip_no,
            "detail_text": text[:DETAIL_TEXT_LIMIT],
            "truncated": len(text) > DETAIL_TEXT_LIMIT,
        }
