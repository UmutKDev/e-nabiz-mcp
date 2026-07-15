"""Radyoloji (görüntüleme) tool'ları.

Liste: GET /Home/RadyolojikGoruntulerim → sayfa-içi `.radyolojiCardListe` kartları.
Rapor: POST /RadyolojikGoruntu/GetRaporByOrder {orderId} → HTML rapor (düz metne indirgenir).

Not: bu alan tablo/`/Index` desenini izlemez; çalışmalar sayfaya render edilir ve
her çalışmanın şifreli bir `order_id` token'ı vardır.
"""

from __future__ import annotations

from fastmcp import FastMCP

from .. import auth
from ..client import xhr_post
from ..config import Config
from ..parsers import html_to_text, parse_radiology_studies
from ._common import apply_limit, auth_guarded

PAGE = "/Home/RadyolojikGoruntulerim"
REPORT_PATH = "/RadyolojikGoruntu/GetRaporByOrder"
IMAGE_LINK_PATH = "/RadyolojikGoruntu/GetGoruntuLinkByOrder"
REPORT_TEXT_LIMIT = 20_000
IMAGE_LINK_MAX_LEN = 2_000  # DICOM görüntüleyici URL'i; bundan uzunsa gövde link değildir


def register(mcp: FastMCP) -> None:
    """Radyoloji tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_radiology_studies(limit: int | None = None) -> dict:
        """E-Nabız radyolojik tetkik/görüntü kayıtlarını listeler.

        Sayfada gösterilen çalışmaları döndürür (tarih, kurum, açıklama). Her kaydın
        `order_id` alanı, raporu almak için `enabiz_get_radiology_report`'a verilir.
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.

        - `limit`: en fazla kaç kayıt döner (varsayılan 50; `0` = sınırsız).
          `truncated: true` ise liste kırpılmıştır.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            html = client.get(PAGE).text
            if 'name="TCKimlikNo"' in html:
                raise auth.AuthRequired("Oturum düşmüş görünüyor.")
            studies = parse_radiology_studies(html)

        studies, env = apply_limit(studies, limit)
        return {
            **env,
            "studies": [s.model_dump() for s in studies],
        }

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_get_radiology_report(order_id: str) -> dict:
        """Bir radyolojik tetkikin raporunu (düz metin) döndürür.

        `order_id`, `enabiz_list_radiology_studies` çıktısındaki ilgili çalışmadan
        alınır. Kimlikli oturum gerektirir.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            token = auth.scrape_token(client, PAGE)
            resp = xhr_post(client, REPORT_PATH, token, {"orderId": order_id}, referer=PAGE)
            text = html_to_text(resp.text)

        truncated = len(text) > REPORT_TEXT_LIMIT
        return {
            "order_id": order_id,
            "report_text": text[:REPORT_TEXT_LIMIT],
            "truncated": truncated,
        }

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_get_radiology_image_link(accession_number: str) -> dict:
        """Bir radyolojik tetkikin DICOM görüntüleyici linkini (URL) döndürür.

        `accession_number`, `enabiz_list_radiology_studies` çıktısındaki ilgili
        çalışmadan alınır (yalnız görüntüsü olan çalışmalarda dolu). Binary değil,
        bir URL döner. Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            token = auth.scrape_token(client, PAGE)
            resp = xhr_post(
                client, IMAGE_LINK_PATH, token, {"AccessionNumber": accession_number}, referer=PAGE
            )
            link = resp.text.strip()

        if not link:
            return {"accession_number": accession_number, "image_link": None}
        # Yanıt gövdesi doğrulanmadan dönerse (WAF ara sayfası, işlenmemiş 5xx) tüm
        # HTML dokümanı "link" diye bağlama enjekte olur. Oturum düşmesi buraya
        # gelmez — scrape_token zaten auth_required fırlatır.
        if not link.startswith(("http://", "https://")) or len(link) > IMAGE_LINK_MAX_LEN:
            return {
                "error": "unexpected_response",
                "message": "Görüntü linki yerine beklenmeyen bir yanıt döndü (URL değil).",
                "hint": "Portal geçici olarak hata veriyor olabilir; sonra tekrar deneyin.",
                "body_preview": link[:200],
            }

        return {"accession_number": accession_number, "image_link": link}

