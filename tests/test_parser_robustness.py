"""Parser sağlamlık testleri — beklenen tablo yoksa ne olur?

İki gizli tehlike kapatıldı (ikisi de bugün canlıda ulaşılamıyordu; portal HTML'i
değişirse tetiklenirdi — bu projenin tüm risk modeli portalın değişmesi).
"""

from __future__ import annotations

import pytest

from enabiz_mcp.parsers import (
    parse_emergency_notes,
    parse_insurance,
    parse_prescriptions,
    parse_reports,
    parse_vaccinations,
)

# Beklenen id'si OLMAYAN ama başka bir tablo İÇEREN sayfa (nav/yerleşim tablosu).
_NAV_PAGE = """<html><body>
  <table id="navMenu"><tbody>
    <tr><td>Ana Sayfa</td><td>Profilim</td><td>Ayarlar</td><td>Çıkış</td>
        <td>Yardım</td><td>Bildirim</td><td>Mesaj</td></tr>
  </tbody></table>
</body></html>"""


@pytest.mark.parametrize(
    "parser",
    [parse_insurance, parse_vaccinations, parse_emergency_notes, parse_reports],
)
def test_missing_table_id_returns_empty_not_garbage(parser):
    """Beklenen id yoksa `[]` dönmeli — sayfadaki İLK tablo değil.

    Eskiden `select_one("#tblX") or soup.find("table")` vardı: id kaybolursa parser
    rastgele bir tabloyu (nav/yerleşim) kapıp kolonlarını sağlık modeline pozisyonel
    eşliyordu. Sağlık verisinde sessiz-bozuk kayıt, boş sonuçtan çok daha kötüdür.
    """
    assert parser(_NAV_PAGE) == []


def test_prescriptions_parses_table_without_tbody():
    """`parse_prescriptions` 19 parser içinde `_rows()` kullanmayan tek sapandı.

    `<tbody>`siz bir tabloda `[]` dönerken diğer tüm parser'lar doğru çalışıyordu.
    """
    html = (
        '<table id="tbl-recetelerim">'
        "<tr><th>Tarih</th><th>No</th><th>Tür</th><th>Hekim</th></tr>"
        "<tr><td>01.01.2024</td><td>RX1</td><td>Normal</td><td>DR TEST</td></tr>"
        "</table>"
    )
    items = parse_prescriptions(html)
    assert len(items) == 1
    assert items[0].prescription_no == "RX1"
    assert items[0].doctor == "DR TEST"


def test_prescriptions_still_parses_table_with_tbody():
    html = (
        '<table id="tbl-recetelerim"><tbody>'
        "<tr><td>02.02.2024</td><td>RX2</td><td>Normal</td><td>DR X</td></tr>"
        "</tbody></table>"
    )
    assert len(parse_prescriptions(html)) == 1
