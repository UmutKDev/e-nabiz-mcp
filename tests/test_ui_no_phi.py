"""TRIPWIRE — panel yolunda PHI model bağlamına GİRMEMELİ (invaryant #3).

Bu dosya, ext-apps katmanının VAROLUŞ SEBEBİNİ makineye bağlar. Panel render
edebilen bir istemcide `enabiz_list_*` yalnız sayı dönmeli; kayıt değerleri
`enabiz_ui_data` ile panele, modeli baypas ederek gitmeli.

Alan adı listesi TUTMUYORUZ (`assert "allergies" not in out` gibi): öyle bir
test, yarın eklenen bir alanı kaçırırdı. Bunun yerine fixture'ın GERÇEK
DEĞERLERİNİ yanıtın tamamında arıyoruz — yeni alan eklense de tripwire tutar.
"""

from __future__ import annotations

import contextlib
import json

import httpx
import pytest
from conftest import fixture_html

from enabiz_mcp import auth
from enabiz_mcp.tools import allergies
from enabiz_mcp.ui import registry

#: `alerji_sample.html` içindeki sentetik ama PHI-ŞEKLİNDE değerler. Panel
#: yolunda bunların HİÇBİRİ modele gitmemeli.
PHI_VALUES = ("PENISILIN", "Kızarıklık", "01.02.2020")


class _FakeMCP:
    """`register()`'ın kaydettiği closure'ları yakalar (test_tools_smoke ile aynı desen)."""

    def __init__(self) -> None:
        self.tools: dict = {}

    def tool(self, **_kw):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn

        return deco


@pytest.fixture
def alerji_tools(monkeypatch):
    """Alerji sayfasını sentetik fixture ile servis eder — ağ yok."""
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
    allergies.register(fake)
    return fake.tools


def _panel_var(monkeypatch, capable: bool) -> None:
    """İstemcinin panel yeteneğini taklit eder."""
    monkeypatch.setattr(allergies, "app_capable", lambda: capable)


def test_panel_yolunda_phi_modele_gitmez(alerji_tools, monkeypatch):
    """Panel varken tool'un yanıtında hiçbir kayıt değeri bulunmamalı."""
    _panel_var(monkeypatch, True)
    out = alerji_tools["enabiz_list_allergies"]()
    dump = json.dumps(out, ensure_ascii=False)

    for phi in PHI_VALUES:
        assert phi not in dump, (
            f"PHI panel yolunda model bağlamına sızdı: {phi!r} → {dump}\n"
            "İnvaryant #3 ihlali — bu tool'un panel dalı yalnız sayı dönmeli."
        )
    assert out["rendered_in_app"] is True
    assert out["count"] == 3  # sayı geçer; asgari uygulanabilir açıklama
    assert out["domain"] in registry.DOMAINS


def test_metin_yolunda_veri_AYNEN_gelir(alerji_tools, monkeypatch):
    """Panel yokken bugünkü davranış birebir sürmeli — sıfır regresyon.

    Bu testin ikizi yukarıdakidir: biri PHI'nın GİTMEDİĞİNİ, bu ise
    GİTTİĞİNİ doğrular. İkisi olmadan "panel PHI'yı kaldırıyor" iddiası
    boştur — veri hiç gelmiyor da olabilirdi.
    """
    _panel_var(monkeypatch, False)
    out = alerji_tools["enabiz_list_allergies"]()
    dump = json.dumps(out, ensure_ascii=False)

    for phi in PHI_VALUES:
        assert phi in dump, f"metin yolu bozuldu: {phi!r} artık dönmüyor"
    assert out["count"] == 3
    assert "rendered_in_app" not in out


def test_panel_yolu_filtreyi_panele_bildirir(alerji_tools, monkeypatch):
    """`category` panele geçmeli — yoksa panel filtresiz liste çeker."""
    _panel_var(monkeypatch, True)
    out = alerji_tools["enabiz_list_allergies"](category="ilac")
    assert out["params"] == {"category": "ilac"}
    assert out["count"] == 2


def test_app_capable_baglamsiz_ortamda_metne_duser():
    """Aktif MCP bağlamı yokken panel yolu SEÇİLMEMELİ (güvenli yön)."""
    from enabiz_mcp.ui import app_capable

    assert app_capable() is False
