"""Epikriz parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_discharge_summaries

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "epikriz_sample.html").read_text(encoding="utf-8")
    items = parse_discharge_summaries(html)
    assert len(items) == 2
    e = items[0]
    assert e.date == "03.03.2022"
    assert e.reference_no == "REF001"
    assert e.hospital == "TEST HASTANE"
    assert e.clinic == "Kardiyoloji"
    assert e.doctor == "DR EPIKRIZ"
    assert e.sys_no == "SYS001"  # PDF için (Faz 4)
