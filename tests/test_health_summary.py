"""`build_health_summary` entegrasyon testleri — ağ yok (httpx.MockTransport)."""

from __future__ import annotations

import httpx
import pytest

from enabiz_mcp import auth
from enabiz_mcp.tools.summary import build_health_summary

_TOKEN = '<input name="__RequestVerificationToken" value="tok"/>'
_PROFILE = "<script>var orgData = { 'Boy':'180','Kilo':'72','KanGrubu':'4' };</script>"
_ALLERGY = ('<table id="tblAlerjilerim"><tbody><tr><td>01.01.2020</td><td>İlaç</td>'
            "<td>X</td><td>Kızarıklık</td></tr></tbody></table>")
_DIAG = ('<table id="tblHastaliklarim"><tbody><tr><td>01.01.2024</td><td>J45</td>'
         "<td>K</td><td>DR</td></tr></tbody></table>")
_ASI = ('<table id="tblAsilar"><tbody><tr><td>01.01.2021</td><td>COVID</td><td>1</td>'
        "<td>ASM</td></tr></tbody></table>")
_RANDEVU = ('<table id="tblRandevuListesi"><tbody><tr><td>01.01.2026</td><td>Kurum</td>'
            "<td>Klinik</td><td>Yer</td><td>DR</td><td>Aktif</td></tr></tbody></table>")
_ILAC = ('<table id="tblIlaclarim"><tbody><tr><td>01.01.2024</td><td>BC</td><td>R1</td>'
         "<td>ILAC</td></tr></tbody></table>")
_ZIYARET = ('<div class="ziyaretCardList"><span class="zTarihS">01.01.2024</span>'
            '<p class="card-text">H</p></div>')

_GET_ROUTES = {
    "/Home/ProfilBilgilerim": _PROFILE,
    "/Home/Alerjilerim": _ALLERGY,
    "/Home/Hastaliklarim": _DIAG,
    "/Home/AsiTakvimi": _ASI,
    "/Home/Randevularim": _RANDEVU,
    "/Home/Ilaclarim": _TOKEN,
    "/Home/Ziyaretlerim": _TOKEN,
}


def _handler(request: httpx.Request) -> httpx.Response:
    p = request.url.path
    if request.method == "GET" and p in _GET_ROUTES:
        return httpx.Response(200, text=_GET_ROUTES[p])
    if request.method == "POST" and p == "/Ilac/Index":
        return httpx.Response(200, text=_ILAC)
    if request.method == "POST" and p == "/Ziyaret/Index":
        return httpx.Response(200, text=_ZIYARET)
    return httpx.Response(404)


def _client(handler=_handler) -> httpx.Client:
    return httpx.Client(base_url="https://enabiz.gov.tr", transport=httpx.MockTransport(handler))


def test_composes_all_domains():
    with _client() as c:
        s = build_health_summary(c, "2020", "2026")
    assert s["profile"]["blood_type"] == "0 Rh+"
    assert s["allergies"]["count"] == 1
    assert s["diagnoses"]["count"] == 1
    assert s["vaccinations"]["count"] == 1
    assert s["appointments"]["count"] == 1
    assert s["medications"]["count"] == 1
    assert s["hospital_visits"]["count"] == 1


def test_isolates_domain_failure():
    def handler(request):
        if request.url.path == "/Home/Hastaliklarim":
            raise httpx.ConnectError("boom")
        return _handler(request)

    with _client(handler) as c:
        s = build_health_summary(c, "2020", "2026")
    assert "error" in s["diagnoses"]  # bir alan patladı
    assert s["allergies"]["count"] == 1  # diğerleri etkilenmedi


def test_auth_dropped_raises():
    def handler(request):
        return httpx.Response(200, text='<input name="TCKimlikNo"/>')

    with _client(handler) as c, pytest.raises(auth.AuthRequired):
        build_health_summary(c, "2020", "2026")
