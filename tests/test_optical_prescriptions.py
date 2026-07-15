"""Optik reçete parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_optical_prescriptions

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "optik_recete_sample.html").read_text(encoding="utf-8")
    items = parse_optical_prescriptions(html)
    assert len(items) == 2
    o = items[0]
    assert o.date == "10.05.2023"
    assert o.prescription_no == "OPT100"
    assert o.type == "Gözlük"
    assert o.doctor == "DR OPTIK A"
    assert items[1].type == "Lens"
