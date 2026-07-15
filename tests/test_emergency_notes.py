"""Acil durum notları parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_emergency_notes

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "acil_sample.html").read_text(encoding="utf-8")
    items = parse_emergency_notes(html)
    assert len(items) == 1
    n = items[0]
    assert n.date == "03.03.2024"
    assert n.subject == "Alerji"
    assert n.description == "Penisilin alerjisi"
