"""Malzeme/cihaz parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_materials_devices

FX = Path(__file__).parent / "fixtures"


def test_counts_categories_and_fields():
    html = (FX / "malzeme_sample.html").read_text(encoding="utf-8")
    items = parse_materials_devices(html)
    assert len(items) == 2  # 1 diger + 1 vucut (isitme boş)
    m = items[0]
    assert m.date == "10.05.2023"
    assert m.category == "diger"
    assert m.brand == "MARKA A"
    assert m.shelf_life == "24 ay"
    assert m.product == "TEST CIHAZ"
    assert items[1].category == "vucut"
    assert items[1].product == "VUCUT CIHAZI"
