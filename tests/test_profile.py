"""Profil parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_profile

FX = Path(__file__).parent / "fixtures"


def test_fields():
    html = (FX / "profil_sample.html").read_text(encoding="utf-8")
    p = parse_profile(html)
    assert p.full_name == "TEST KULLANICI"
    assert p.birth_date == "01.01.1990"
    assert p.blood_type == "0 Rh+"  # orgData KanGrubu=4
    assert p.height_cm == "180"
    assert p.weight_kg == "72,5"
    assert p.family_physician and "Aile" in p.family_physician


def test_empty_input_all_none():
    p = parse_profile("<html><body></body></html>")
    assert p.full_name is None
    assert p.blood_type is None
    assert p.height_cm is None
    assert p.weight_kg is None
