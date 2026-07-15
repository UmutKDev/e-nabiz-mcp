"""Kronik hastalık takip parser'ı için birim testleri (sentetik, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_chronic_followups

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "hastalik_takip_sample.html").read_text(encoding="utf-8")
    items = parse_chronic_followups(html)
    assert len(items) == 2
    c = items[0]
    assert c.followup_type == "Kronik Takip"
    assert c.chronic_disease == "Hipertansiyon"
    assert c.followup_date == "01.03.2024"
    assert c.planned_date == "01.06.2024"
    assert c.realized == "Evet"
    assert c.sys_takip_no == "TK01"
    assert items[1].realized == "Hayır"
