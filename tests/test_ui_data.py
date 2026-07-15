"""`enabiz_ui_data` — panelin çağırdığı arka-uç tool'u.

Model bu tool'u görmez, ama panel ona bağımlıdır: bozulursa panel boş açılır.
"""

from __future__ import annotations

import contextlib

import httpx
import pytest
from conftest import fixture_html

from enabiz_mcp import auth
from enabiz_mcp.ui import tools as ui_tools
from enabiz_mcp.ui.tools import MAX_PAYLOAD_CHARS, _fit


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict = {}
        self.kwargs: dict = {}

    def tool(self, **kw):
        def deco(fn):
            self.tools[fn.__name__] = fn
            self.kwargs[fn.__name__] = kw
            return fn

        return deco


@pytest.fixture
def ui_data(monkeypatch):
    client = httpx.Client(
        base_url="https://enabiz.gov.tr",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, text=fixture_html("alerji_sample"))
        ),
    )

    @contextlib.contextmanager
    def fake_scope(_cfg):
        yield client

    monkeypatch.setattr(auth, "session_scope", fake_scope)
    fake = _FakeMCP()
    ui_tools.register(fake)
    return fake


def test_model_gormez(ui_data):
    """`visibility:["app"]` — bu tool modelin tool listesinde YER ALMAMALI."""
    app = ui_data.kwargs["enabiz_ui_data"]["app"]
    assert app.visibility == ["app"]


def test_panele_sema_ve_kayitlari_verir(ui_data):
    out = ui_data.tools["enabiz_ui_data"](domain="allergies")
    assert out["title"] == "Alerjiler"
    assert out["count"] == 3
    assert out["total"] == 3
    assert out["truncated"] is False
    assert [c["key"] for c in out["columns"]][0] == "date"
    # PHI panele GİDER — burası zaten paneldir; invaryant #3 modeli korur, paneli değil.
    assert out["rows"][0]["drug_name"] == "PENISILIN"


def test_filtre_gecer(ui_data):
    out = ui_data.tools["enabiz_ui_data"](domain="allergies", params={"category": "ilac"})
    assert out["count"] == 2


def test_bilinmeyen_domain_hata_doner(ui_data):
    out = ui_data.tools["enabiz_ui_data"](domain="yok_boyle_bir_sey")
    assert out["error"] == "unknown_domain"
    assert "allergies" in out["known"]


def test_bilinmeyen_parametre_sessizce_dusurulmez(ui_data):
    """Düşürülseydi panel filtreli sandığı listeyi filtresiz gösterirdi (invaryant #2)."""
    out = ui_data.tools["enabiz_ui_data"](domain="allergies", params={"uydurma": 1})
    assert out["error"] == "unknown_params"
    assert "uydurma" in out["message"]


def test_oturum_dusunce_hata_sozlugu_doner(monkeypatch):
    """`auth_guarded` panel tool'unda da geçerli — panel çökmez, hata gösterir."""

    @contextlib.contextmanager
    def dead_scope(_cfg):
        raise auth.AuthRequired("Oturum düşmüş görünüyor.")
        yield  # pragma: no cover

    monkeypatch.setattr(auth, "session_scope", dead_scope)
    fake = _FakeMCP()
    ui_tools.register(fake)
    out = fake.tools["enabiz_ui_data"](domain="allergies")
    assert out["error"] == "auth_required"


def test_fit_tavani_asmaz_ve_kirpmayi_beyan_eder():
    """Payload tavanı aşılırsa host yanıtı dosya-işaretçisiyle değiştirir ve
    paneldeki `JSON.parse` boyut ipucu OLMADAN patlar — sessiz ölüm."""
    base = {"domain": "d", "title": "t", "columns": [], "empty_text": ""}
    sisman = [{"x": "a" * 1000} for _ in range(500)]  # ~500k karakter
    rows, kirpildi = _fit(sisman, base)
    assert kirpildi is True
    assert 0 < len(rows) < len(sisman)
    import json

    assert len(json.dumps({**base, "rows": rows}, ensure_ascii=False)) <= MAX_PAYLOAD_CHARS


def test_fit_siga_kirpmaz():
    base = {"domain": "d", "title": "t", "columns": [], "empty_text": ""}
    rows = [{"x": "kisa"} for _ in range(3)]
    out, kirpildi = _fit(rows, base)
    assert kirpildi is False
    assert out == rows
