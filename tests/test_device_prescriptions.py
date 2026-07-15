"""Tıbbi cihaz reçete parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_device_prescriptions

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "cihaz_recete_sample.html").read_text(encoding="utf-8")
    items = parse_device_prescriptions(html)
    assert len(items) == 2
    c = items[0]
    assert c.date == "15.06.2022"
    assert c.prescription_no == "CIH100"
    assert c.doctor == "DR CIHAZ A"
    assert c.facility == "TEST TIP MERKEZI"
    assert items[1].facility == "X HASTANE"
