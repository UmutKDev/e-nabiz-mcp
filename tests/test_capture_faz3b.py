"""`scripts/capture_faz3b.py` saf çıkarım yardımcıları — sentetik, ağ yok."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "capture_faz3b", Path(__file__).resolve().parent.parent / "scripts" / "capture_faz3b.py"
)
cap = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cap)  # type: ignore[union-attr]


def test_first_islem_tipi():
    html = "<div><a onclick=\"GrafikGoster('HGB')\">Grafik</a></div>"
    assert cap._first_islem_tipi(html) == "HGB"
    assert cap._first_islem_tipi("<div>yok</div>") is None


def test_first_visit_detail_qs():
    html = (
        "<a onclick=\"openModal({url:'/Ziyaret/GetZiyaretDetay?data=TOK&amp;hastane=H"
        "&amp;brans=B&amp;hastaneKod=K&amp;hekim=DR'})\">Detay</a>"
    )
    qs = cap._first_visit_detail_qs(html)
    assert qs is not None and qs.startswith("data=TOK")
    assert "hastane=H" in qs  # &amp; BeautifulSoup tarafından çözülür
    assert cap._first_visit_detail_qs("<a onclick=\"foo()\">x</a>") is None


def test_structure_is_phi_safe_structure_only():
    html = (
        '<table id="tblTahlilCovid19"><thead><tr><th>Tarih</th><th>Test</th>'
        "<th>Sonuç</th></tr></thead><tbody><tr><td>x</td></tr><tr><td>y</td></tr>"
        "</tbody></table>"
    )
    st = cap._structure(html)
    assert st["tables"]["tblTahlilCovid19"]["columns"] == ["Tarih", "Test", "Sonuç"]
    assert st["tables"]["tblTahlilCovid19"]["rows"] == 2
    assert "byte_size" in st
