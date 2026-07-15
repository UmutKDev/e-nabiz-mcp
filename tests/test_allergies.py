"""Alerji parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_allergies

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "alerji_sample.html").read_text(encoding="utf-8")
    items = parse_allergies(html)
    assert len(items) == 3  # 2 ilaç + 1 tanı-bazlı (deri boş)
    a = items[0]
    assert a.date == "01.02.2020"
    assert a.category == "ilac"
    assert a.allergy_type == "İlaç Alerjisi"
    assert a.drug_name == "PENISILIN"
    assert a.symptoms == "Kızarıklık"
    # Kategori etiketleme tabloya göre doğru mu
    assert items[1].category == "ilac"
    assert items[2].category == "tani"
    assert items[2].allergy_type == "Tanı Bazlı"
