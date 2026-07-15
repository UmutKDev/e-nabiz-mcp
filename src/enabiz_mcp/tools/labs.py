"""Tahlil (laboratuvar) tool'ları.

Endpoint: POST /Tahlil/Index {baslangicTarihi(yıl), bitisTarihi(yıl), activeTab}
→ HTML accordion partial (bkz. parsers.parse_lab_reports).
"""

from __future__ import annotations

import datetime

from fastmcp import FastMCP

from .. import auth
from .._text import tr_contains
from ..client import xhr_post
from ..config import Config
from ..parsers import parse_lab_reports, parse_lab_trend
from ._common import DEFAULT_LIMIT, auth_guarded

LAB_INDEX_PATH = "/Tahlil/Index"
LAB_PAGE = "/Home/Tahlillerim"
TREND_PATH = "/Tahlil/TahlillerRapor"


def _take_tests(reports: list, limit: int) -> list:
    """Toplam test sonucu `limit`'i aşmayacak şekilde raporları kırpar.

    Raporlar sırayla eklenir; sınıra ortasında ulaşılan rapor kısmi sonuçla girer
    (rapor bağlamı — tarih/kurum — korunsun diye). `limit` 0/negatifse sınırsız.
    """
    if limit <= 0:
        return reports
    out, budget = [], limit
    for rep in reports:
        if budget <= 0:
            break
        if len(rep.results) > budget:
            rep = rep.model_copy(update={"results": rep.results[:budget]})
        budget -= len(rep.results)
        out.append(rep)
    return out


def register(mcp: FastMCP) -> None:
    """Tahlil tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_list_lab_tests(
        start_year: int | None = None,
        end_year: int | None = None,
        test_query: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız tahlil (laboratuvar) sonuçlarını yıl aralığına göre listeler.

        - `start_year` / `end_year`: yıl aralığı. Verilmezse son 6 takvim yılı
          (bu yıl - 5 … bu yıl).
        - `test_query`: verilirse test adında büyük/küçük harf duyarsız filtre uygular.
          Belirli bir testi arıyorsanız MUTLAKA kullanın — yanıt aksi hâlde çok büyük olur.
        - `limit`: en fazla kaç TEST SONUCU döner (varsayılan 50; `0` = sınırsız).
          Raporlar en yeniden başlayarak bu sayıya ulaşana dek eklenir.

        `truncated: true` ise liste kırpılmıştır — `test_query` ile daraltın.
        Kimlikli oturum gerektirir; oturum yoksa/düşmüşse `error: "auth_required"`
        döner. Sonuçlar tarih/ziyaret bazlı gruplanır.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            token = auth.scrape_token(client, LAB_PAGE)
            this_year = datetime.date.today().year
            end = end_year or this_year
            start = start_year or (this_year - 5)
            resp = xhr_post(
                client,
                LAB_INDEX_PATH,
                token,
                {
                    "baslangicTarihi": str(start),
                    "bitisTarihi": str(end),
                    "activeTab": "0",
                },
                referer=LAB_PAGE,
            )
            reports = parse_lab_reports(resp.text)

        if test_query:
            filtered = []
            for rep in reports:
                hits = [r for r in rep.results if tr_contains(test_query, r.test)]
                if hits:
                    rep.results = hits
                    filtered.append(rep)
            reports = filtered

        # Token yükü iç içe `results`'ta: bir rapor çok sayıda test taşır. Rapor
        # sayısını sınırlamak işe yaramaz (15 < 50) — sınır TEST sonucuna konur.
        total_tests = sum(len(r.results) for r in reports)
        total_reports = len(reports)
        reports = _take_tests(reports, DEFAULT_LIMIT if limit is None else limit)
        shown_tests = sum(len(r.results) for r in reports)

        return {
            "year_range": [start, end],
            "report_count": len(reports),
            "total_reports": total_reports,
            "test_count": shown_tests,
            "total_tests": total_tests,
            "truncated": shown_tests < total_tests,
            "reports": [r.model_dump() for r in reports],
        }

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_get_lab_trend(islem_tipi: str) -> dict:
        """Bir tahlil testinin zaman içindeki trendini (geçmiş ölçümler) döndürür.

        `islem_tipi` = `enabiz_list_lab_tests` çıktısındaki bir sonucun `trend_code`
        alanı (görünen test adından farklı olabilir; her zaman `trend_code`'u geçin).
        Her nokta tarih, sonuç, birim ve referans değeri ile döner.
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            resp = client.get(TREND_PATH, params={"IslemTipi": islem_tipi})
            html = resp.text
            if 'name="TCKimlikNo"' in html:
                raise auth.AuthRequired("Oturum düşmüş görünüyor.")
            points = parse_lab_trend(html)

        return {
            "islem_tipi": islem_tipi,
            "count": len(points),
            "points": [p.model_dump() for p in points],
        }

