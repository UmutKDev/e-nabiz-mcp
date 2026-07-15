"""Radyoloji parser'ları için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import html_to_text, parse_radiology_studies

FX = Path(__file__).parent / "fixtures"


def test_studies_counts_and_fields():
    html = (FX / "radyoloji_sample.html").read_text(encoding="utf-8")
    st = parse_radiology_studies(html)
    assert len(st) == 2
    s = st[0]
    assert s.date == "07.01.2026"  # "07.01.2026 07.01.2026" → ilk tarih
    assert s.hospital == "TEST HASTANESI A"
    assert s.description == "BT TORAKS"
    assert s.order_id == "TOKEN111"
    assert s.accession_number == "ACC111"  # openImageLink('ACC111') → görüntü linki
    assert st[1].order_id == "TOKEN222"
    assert st[1].accession_number is None  # 2. kartta görüntü butonu yok


def test_report_text_strips_script_and_style():
    html = (
        "<html><head><style>.x{color:red}</style></head>"
        "<body><script>bad()</script><p>BULGU: normal.</p></body></html>"
    )
    txt = html_to_text(html)
    assert "BULGU: normal." in txt
    assert "bad()" not in txt
    assert "color:red" not in txt
