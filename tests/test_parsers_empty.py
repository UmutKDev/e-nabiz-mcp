"""Her liste parser'ı boş/kayıtsız sayfada `[]` dönmeli — asla patlamamalı.

Bu sözleşme 17 dosyada birebir aynı `test_empty_input` olarak kopyalanmıştı.
Kapsam aynı, tek yerde. (`parse_profile` ve `parse_visit_detail` burada değil:
liste değil, sırasıyla model ve dict döndürürler — kendi testlerinde kalırlar.)
"""

from __future__ import annotations

import pytest

from enabiz_mcp import parsers as P

_LIST_PARSERS = [
    P.parse_allergies,
    P.parse_appointments,
    P.parse_chronic_followups,
    P.parse_device_prescriptions,
    P.parse_diagnoses,
    P.parse_discharge_summaries,
    P.parse_drug_usage_history,
    P.parse_emergency_notes,
    P.parse_hospital_visits,
    P.parse_insurance,
    P.parse_lab_reports,
    P.parse_lab_trend,
    P.parse_materials_devices,
    P.parse_medications,
    P.parse_optical_prescriptions,
    P.parse_pathology,
    P.parse_prescriptions,
    P.parse_radiology_studies,
    P.parse_reports,
    P.parse_vaccinations,
]

_EMPTY_PAGES = [
    "<html><body>Kayıt yok</body></html>",
    "<html><body>Kayıt Bulunamadı!</body></html>",
    "<html><body></body></html>",
    "",
]


@pytest.mark.parametrize("parser", _LIST_PARSERS, ids=lambda f: f.__name__)
@pytest.mark.parametrize("html", _EMPTY_PAGES, ids=["kayit-yok", "bulunamadi", "bos-body", "bos"])
def test_list_parsers_return_empty(parser, html):
    assert parser(html) == []


@pytest.mark.parametrize("html", _EMPTY_PAGES, ids=["kayit-yok", "bulunamadi", "bos-body", "bos"])
def test_prescription_detail_returns_empty(html):
    """`list[dict]` döndürür (model değil) — bu yüzden yukarıdaki listede değil."""
    assert P.parse_prescription_detail(html) == []
