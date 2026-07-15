"""Randevu parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_appointments

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "randevu_sample.html").read_text(encoding="utf-8")
    ap = parse_appointments(html)
    assert len(ap) == 2
    a = ap[0]
    assert a.date_time == "15.08.2026 14:30"
    assert a.institution == "TEST HASTANESI"
    assert a.clinic == "DAHILIYE"
    assert a.location == "Poliklinik 3"
    assert a.doctor == "DR TEST BIR"
    assert a.status == "Aktif"
    assert a.type == "MHRS"
    assert ap[1].status == "Geçmiş"
