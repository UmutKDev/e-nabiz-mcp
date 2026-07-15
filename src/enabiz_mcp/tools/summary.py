"""Sağlık özeti tool'u (salt-okunur derleyici).

`enabiz_get_health_summary` birden çok alanı tek çağrıda derler (profil + alerjiler +
tanılar + aşılar + ilaçlar + ziyaretler + randevular). Alan başına hata izole edilir
(biri düşerse diğerleri döner). Tek `session_scope` içinde, hız sınırına uyarak çalışır.
"""

from __future__ import annotations

import datetime

from fastmcp import FastMCP

from .. import auth
from ..client import xhr_post
from ..config import Config
from ..parsers import (
    parse_allergies,
    parse_appointments,
    parse_diagnoses,
    parse_hospital_visits,
    parse_medications,
    parse_profile,
    parse_vaccinations,
)
from ._common import auth_guarded


def build_health_summary(client, y0: str, y1: str) -> dict:
    """Verilen kimlikli istemciyle alanlar arası özeti derler (alan başına izole hata).

    Oturum düşmüşse (profil sayfası login'e yönlenmiş) `AuthRequired` fırlatır.
    """
    summary: dict = {}
    html = client.get("/Home/ProfilBilgilerim").text
    if 'name="TCKimlikNo"' in html:
        raise auth.AuthRequired("Oturum düşmüş görünüyor.")
    prof = parse_profile(html)
    summary["profile"] = {
        "blood_type": prof.blood_type,
        "height_cm": prof.height_cm,
        "weight_kg": prof.weight_kg,
    }

    def _safe(key, fn):
        try:
            summary[key] = fn()
        except Exception as exc:  # noqa: BLE001 — alan başına izolasyon
            summary[key] = {"error": type(exc).__name__}

    def _get(path):
        return client.get(path).text

    def _post_index(list_path, page, params):
        token = auth.scrape_token(client, page)
        return xhr_post(client, list_path, token, params, referer=page).text

    _safe("allergies", lambda: {
        "count": len(a := parse_allergies(_get("/Home/Alerjilerim"))),
        "allergies": [x.model_dump() for x in a],
    })
    _safe("diagnoses", lambda: {"count": len(parse_diagnoses(_get("/Home/Hastaliklarim")))})
    _safe("vaccinations", lambda: {"count": len(parse_vaccinations(_get("/Home/AsiTakvimi")))})
    _safe("appointments", lambda: {
        "count": len(ap := parse_appointments(_get("/Home/Randevularim"))),
        "appointments": [x.model_dump() for x in ap],
    })
    _safe("medications", lambda: {"count": len(parse_medications(
        _post_index("/Ilac/Index", "/Home/Ilaclarim", {"baslangicYil": y0, "bitisYil": y1})
    ))})
    _safe("hospital_visits", lambda: {"count": len(parse_hospital_visits(
        _post_index("/Ziyaret/Index", "/Home/Ziyaretlerim", {"baslangicYil": y0, "bitisYil": y1})
    ))})
    return summary


def register(mcp: FastMCP) -> None:
    """Sağlık özeti tool'unu verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_get_health_summary() -> dict:
        """Birden çok alanı tek çağrıda derleyen salt-okunur sağlık özeti.

        Döner: profil (kan grubu/boy/kilo), alerjiler (liste — güvenlik-kritik),
        tanı/aşı/ilaç/ziyaret sayıları ve randevular. Bir alan alınamazsa o alan
        `{"error": ...}` olur, diğerleri etkilenmez. Kimlikli oturum gerektirir;
        yoksa `error: "auth_required"`.
        """
        cfg = Config.from_env()
        this_year = datetime.date.today().year
        with auth.session_scope(cfg) as client:
            return build_health_summary(client, str(this_year - 5), str(this_year))
