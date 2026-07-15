"""Sigorta parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_insurance

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "sigorta_sample.html").read_text(encoding="utf-8")
    items = parse_insurance(html)
    assert len(items) == 2
    s = items[0]
    assert s.description == "SGK"
    assert s.insurance_code == "SGK001"
    assert s.date_range == "01.01.2020 - 01.01.2025"
    assert s.extra_period == "-"
    assert s.status == "Aktif"
    assert items[1].status == "Pasif"
