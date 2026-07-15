"""İlaç kullanım geçmişi parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_drug_usage_history

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "ilac_gecmis_sample.html").read_text(encoding="utf-8")
    items = parse_drug_usage_history(html)
    assert len(items) == 2
    u = items[0]
    assert u.date == "10.01.2024"
    assert u.barcode == "8699999000001"
    assert u.name == "TEST ILAC"
    assert u.description == "Film Tablet"
    assert u.dose == "1"
    assert u.usage_count == "2"
    assert u.period == "Günde"
    assert u.usage_form == "Ağızdan"
