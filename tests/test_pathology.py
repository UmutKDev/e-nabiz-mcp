"""Patoloji parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_pathology

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "patoloji_sample.html").read_text(encoding="utf-8")
    items = parse_pathology(html)
    assert len(items) == 2
    p = items[0]
    assert p.date == "08.08.2021"
    assert p.reference_no == "PREF001"
    assert p.hospital == "PAT HASTANE"
    assert p.clinic == "Patoloji"
    assert p.doctor == "DR PAT"
    assert p.sys_no == "PSYS001"  # PDF için (Faz 4)
