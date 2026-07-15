"""Rapor parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_reports

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "rapor_list_sample.html").read_text(encoding="utf-8")
    rs = parse_reports(html)
    assert len(rs) == 2
    r = rs[0]
    assert r.date == "12.03.2024"
    assert r.report_no == "R100"
    assert r.tracking_no == "TK900"
    assert r.type == "İlaç Kullanım Raporu"
    assert r.start_date == "12.03.2024"
    assert r.end_date == "12.03.2025"
    assert r.diagnosis == "TEST TANI A"
