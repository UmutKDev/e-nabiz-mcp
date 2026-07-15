"""İlaç parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_medications

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "ilac_list_sample.html").read_text(encoding="utf-8")
    ms = parse_medications(html)
    assert len(ms) == 2
    m = ms[0]
    assert m.prescription_date == "10.05.2024"
    assert m.barcode == "8699111"
    assert m.prescription_no == "ABC123"
    assert m.name == "TEST ILAC A 500 MG"
    assert m.dose == "1x1"
    assert m.usage == "Ağızdan"
    assert m.box_count == "1"
    assert m.hospital == "TEST HASTANESI"
    assert m.clinic == "DAHILIYE"
