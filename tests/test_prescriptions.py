"""Reçete parser'ları için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_prescription_detail, parse_prescriptions

FX = Path(__file__).parent / "fixtures"


def test_list_counts_and_fields():
    html = (FX / "recete_list_sample.html").read_text(encoding="utf-8")
    ps = parse_prescriptions(html)
    assert len(ps) == 2
    p = ps[0]
    assert p.date == "10.05.2024"
    assert p.prescription_no == "ABC123"
    assert p.type == "Normal Reçete"
    assert p.doctor == "DR TEST BIR"
    assert p.sys_takip_no == "SYS111"


def test_detail_categories_and_fields():
    html = (FX / "recete_detail_sample.html").read_text(encoding="utf-8")
    drugs = parse_prescription_detail(html)
    assert len(drugs) == 2

    cats = [d["category"] for d in drugs]
    assert cats.count("prescribed") == 1
    assert cats.count("dispensed") == 1

    prescribed = next(d for d in drugs if d["category"] == "prescribed")
    assert prescribed["barcode"] == "8699111"
    assert prescribed["name"] == "TEST ILAC A 500 MG"
    assert prescribed["dose"] == "1x1"
    assert prescribed["box_count"] == "1"

    dispensed = next(d for d in drugs if d["category"] == "dispensed")
    assert dispensed["barcode"] == "8699222"
    assert dispensed["box_count"] == "1"
