"""Ziyaret detayı parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_visit_detail

FX = Path(__file__).parent / "fixtures"


def test_diagnoses_and_procedures():
    html = (FX / "ziyaret_detay_sample.html").read_text(encoding="utf-8")
    d = parse_visit_detail(html)

    assert len(d["diagnoses"]) == 1
    tani = d["diagnoses"][0]
    assert tani["date"] == "03.03.2024"
    assert tani["diagnosis"] == "I10 - HIPERTANSIYON"
    assert tani["doctor"] == "DR TANI"
    assert tani["clinic"] == "Kardiyoloji"

    assert d["preliminary_diagnoses"] == []
    assert d["additional_diagnoses"] == []

    assert len(d["procedures"]) == 2
    proc = d["procedures"][0]
    assert proc["procedure_time"] == "03.03.2024 10:00"
    assert proc["appointment_time"] == "03.03.2024 09:30"
    assert proc["count"] == "1"
    assert proc["procedure_name"] == "MUAYENE"


def test_empty_input():
    d = parse_visit_detail("<html><body>yok</body></html>")
    assert d == {
        "diagnoses": [],
        "preliminary_diagnoses": [],
        "additional_diagnoses": [],
        "procedures": [],
    }
