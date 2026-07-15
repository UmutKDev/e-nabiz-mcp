"""`parse_lab_reports` için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp.parsers import parse_lab_reports

FIXTURE = Path(__file__).parent / "fixtures" / "tahlil_sample.html"


def _html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_report_and_test_counts():
    reports = parse_lab_reports(_html())
    assert len(reports) == 2
    assert sum(len(r.results) for r in reports) == 4


def test_date_and_hospital():
    reports = parse_lab_reports(_html())
    assert reports[0].date == "15.Tem.2024"
    assert reports[0].hospital == "TEST HASTANESI A"
    assert reports[1].date == "03.Oca.2023"
    assert reports[1].hospital == "TEST HASTANESI B"


def test_lab_pdf_params_from_pdf_button():
    # .pdfBtnSmall onclick TahlillerPdfIndir('dil','cardTarih','kurumKodu') → PDF paramları
    r = parse_lab_reports(_html())[0]
    assert r.card_tarih == "15.07.2024"
    assert r.kurum_kodu == "K12345"


def test_result_fields_mapped():
    glukoz = parse_lab_reports(_html())[0].results[0]
    # Değerler etiket prefix'i ("Sonuç :", "İşlem Adı :") İÇERMEZ (Bug B)
    assert glukoz.test == "GLUKOZ"
    assert glukoz.value == "95"
    assert glukoz.unit == "mg/dL"
    assert glukoz.reference == "70-100"
    assert glukoz.status == "normal"
    assert glukoz.trend_code == "GLUKOZ"  # GrafikGoster('GLUKOZ') → trend için IslemTipi
    assert glukoz.out_of_range is False  # 95, 70-100 aralığında


def test_out_of_range_flags_server_missed_upper_bound():
    # HOMA-IR: sunucu durumNormal demiş (status normal) ama biz 8,54 > 2,7 → out_of_range
    reports = parse_lab_reports(_html())
    homa = next(r for rep in reports for r in rep.results if r.test == "HOMA-IR")
    assert homa.reference == "-2,7"  # etiket temiz
    assert homa.status == "normal"  # sunucuya sadık
    assert homa.out_of_range is True  # bizim bağımsız kontrolümüz yakaladı


def test_out_of_range_agrees_with_server_two_bound():
    results = [r for rep in parse_lab_reports(_html()) for r in rep.results]
    kol = next(r for r in results if r.test == "KOLESTEROL")
    assert kol.status == "ref_disi"  # sunucu 240 > 200'ü işaretlemiş
    assert kol.out_of_range is True


def test_status_mapping():
    reports = parse_lab_reports(_html())
    statuses = [r.status for rep in reports for r in rep.results]
    assert statuses.count("normal") == 3  # GLUKOZ, HOMA-IR, HEMOGLOBIN
    assert statuses.count("ref_disi") == 1  # KOLESTEROL


def test_compute_out_of_range_formats():
    from enabiz_mcp.parsers import _compute_out_of_range as oor

    assert oor("95", "70-100") is False        # iki uçlu, içeride
    assert oor("240", "0-200") is True          # iki uçlu, üstünde
    assert oor("9,3", "9,3-12,1") is False       # sınırda in-range (virgüllü ondalık)
    assert oor("8,54", "-2,7") is True           # tek üst sınır aşımı
    assert oor("2,0", "-2,7") is False           # tek üst sınır içinde
    assert oor("1", "5-") is True                # tek alt sınır altında
    assert oor("30", "<25") is True
    assert oor("5", ">10") is True
    # değerlendiremeyenler → None (yanlış-pozitif yok)
    assert oor("Pozitif", "Negatif") is None
    assert oor("5", "-") is None
    assert oor("5", "") is None
    assert oor(None, "0-10") is None
    assert oor("abc", "0-10") is None


def test_num_rejects_non_finite():
    """`float()` "nan"/"inf" dizelerini kabul eder — güvenlik-kritik alanda elenmeli.

    Eleme olmadan `_compute_out_of_range("nan", "0-10")` False ("aralıkta") dönerdi:
    nan karşılaştırmalarının tamamı False olduğu için — yani yanlış-negatif.
    Gerçek veride ulaşılamıyor (933 canlı sonuçta sıfır nan/inf); girdi doğrulama
    boşluğu olarak kapatıldı. NOT: `inf` zaten doğru davranıyordu (True dönüyordu).
    """
    from enabiz_mcp.parsers import _compute_out_of_range as oor
    from enabiz_mcp.parsers import _num

    assert _num("nan") is None
    assert _num("inf") is None
    assert _num("-inf") is None
    assert _num("5,5") == 5.5  # normal yol bozulmadı

    assert oor("nan", "0-10") is None  # eskiden False idi
    assert oor("inf", "0-10") is None
