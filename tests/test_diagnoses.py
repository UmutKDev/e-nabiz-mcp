"""Tanı parser'ı + detay metin indirgeme için birim testleri (sentetik, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import html_to_text, parse_diagnoses

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "hastalik_sample.html").read_text(encoding="utf-8")
    items = parse_diagnoses(html)
    assert len(items) == 2
    d = items[0]
    assert d.date == "01.01.2024 12:00"
    assert d.diagnosis == "J45 - ASTIM"
    assert d.clinic == "Göğüs Hastalıkları"
    assert d.doctor == "DR TEST A"
    assert d.sys_takip_no == "TOKEN001"


def test_token_extraction_survives_comma_in_diagnosis():
    # tani argümanı virgüllü ICD içerse bile SysTakipNo (son argüman) doğru gelmeli.
    html = (FX / "hastalik_sample.html").read_text(encoding="utf-8")
    items = parse_diagnoses(html)
    assert items[1].diagnosis == "E11,E10 - DIYABET"
    assert items[1].sys_takip_no == "TOKEN002"


def test_html_to_text_strips_script_and_style():
    html = "<div>Rapor<script>x=1</script><style>.a{}</style> metni</div>"
    text = html_to_text(html)
    assert "Rapor" in text and "metni" in text
    assert "x=1" not in text and ".a{}" not in text
