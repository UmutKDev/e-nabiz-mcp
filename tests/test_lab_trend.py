"""Tahlil trend parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_lab_trend

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "tahlil_trend_sample.html").read_text(encoding="utf-8")
    points = parse_lab_trend(html)
    assert len(points) == 2
    p = points[0]
    assert p.date == "15.07.2024"
    assert p.value == "95"
    assert p.unit == "mg/dL"
    assert p.reference == "70-100"
