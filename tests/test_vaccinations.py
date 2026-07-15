"""Aşı parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_vaccinations

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "asi_sample.html").read_text(encoding="utf-8")
    items = parse_vaccinations(html)
    assert len(items) == 2
    v = items[0]
    assert v.date == "12.04.2021"
    assert v.vaccine == "COVID-19 AŞISI"
    assert v.dose == "1"
    assert v.location == "ANKARA ASM"
    assert items[1].vaccine == "GRIP AŞISI"
