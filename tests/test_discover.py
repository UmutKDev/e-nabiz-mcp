"""Keşif (discovery) saf mantık testleri — ağ yok, sentetik HTML.

`enabiz_mcp.discovery` yalnızca saf fonksiyonlar içerir (HTML→endpoint çıkarımı,
salt-okunur sınıflama, honeypot filtresi, PHI-güvenli rapor). Canlı tarama/giriş
`scripts/discover.py`'dedir ve burada test edilmez (insan-döngüde OTP gerektirir).
"""

from __future__ import annotations

import pytest

from enabiz_mcp import discovery as d

# Gerçek portal desenini birebir taklit eden sentetik (uydurma) script — PHI yok.
_RAPOR_PAGE = """
<html><body>
<select id="baslangicyilSelect"><option value="2019">2019</option>
<option value="2024" selected>2024</option></select>
<select id="bitisyilSelect"><option value="2025" selected>2025</option></select>
<script>
  function GetRaporByDateList(){
    $.ajax({
        url: '/Rapor/Index',
        data: { startYear: baslangicTarihi, endYear: bitisTarihi },
        method: 'POST',
        success: (data) => {
            $('#tblRaporlarim').DataTable().destroy();
            $('#pills-raporlarim').html(data);
        }
    });
  }
  $.ajax({ url: '/Home/GetASMBilgileri', method: 'GET',
           success: function(d){ $('#asmContainer').html(d); } });
  // Yazma çağrısı — replay EDİLMEMELİ
  $.ajax({ url: '/Profil/KiloBoyGuncelle', data: { kilo: x, boy: y }, method: 'POST' });
</script>
</body></html>
"""

# Sunucu-render (AJAX'sız) sayfa — kartlar + tablo doğrudan sayfada.
_SERVER_RENDERED = """
<html><body>
<div class="radyolojiCardListe">a</div>
<div class="radyolojiCardListe">b</div>
<table id="tblRandevuListesi"><tbody>
  <tr><td>x</td></tr><tr><td>y</td></tr><tr><td>z</td></tr>
</tbody></table>
</body></html>
"""


# --------------------------------------------------------------------------- #
# extract_ajax_endpoints
# --------------------------------------------------------------------------- #
def test_extract_finds_all_ajax_calls():
    eps = d.extract_ajax_endpoints(_RAPOR_PAGE)
    by_url = {e.url: e for e in eps}
    assert set(by_url) == {"/Rapor/Index", "/Home/GetASMBilgileri", "/Profil/KiloBoyGuncelle"}


def test_extract_captures_method_params_and_container():
    ep = {e.url: e for e in d.extract_ajax_endpoints(_RAPOR_PAGE)}["/Rapor/Index"]
    assert ep.method == "POST"
    assert ep.param_names == ["startYear", "endYear"]  # yalnız anahtar adları
    assert ep.container == "#tblRaporlarim"  # success içindeki ilk $('#...') sink


def test_extract_get_method_and_no_params():
    ep = {e.url: e for e in d.extract_ajax_endpoints(_RAPOR_PAGE)}["/Home/GetASMBilgileri"]
    assert ep.method == "GET"
    assert ep.param_names == []


def test_extract_strips_query_string_from_url():
    html = "<script>$.ajax({url:'/Recete/GetReceteDetay?data=' + x, method:'POST'});</script>"
    ep = d.extract_ajax_endpoints(html)[0]
    assert ep.url == "/Recete/GetReceteDetay"


def test_extract_empty_when_no_ajax():
    assert d.extract_ajax_endpoints(_SERVER_RENDERED) == []


# --------------------------------------------------------------------------- #
# classify_action — salt-okunur güvenlik
# --------------------------------------------------------------------------- #
def test_classify_read_endpoints():
    assert d.classify_action("/Rapor/Index") == "read"
    assert d.classify_action("/Home/GetASMBilgileri") == "read"
    assert d.classify_action("/Recete/GetReceteDetay") == "read"
    assert d.classify_action("/HastaneZiyaret/SonHastaneZiyareti") == "read"


def test_classify_write_endpoints_are_never_read():
    for url in (
        "/Profil/KiloBoyGuncelle",
        "/Randevu/RandevuAl",
        "/Randevu/RandevuIptal",
        "/Rapor/RaporGizle",
        "/RadyolojikGoruntu/GoruntuGizle",
        "/Recete/IlacHatirlatmasiEkle",
        "/Account/Logout",
        "/Account/SetLanguage",
    ):
        assert d.classify_action(url) == "write", url


def test_classify_unknown_is_not_read():
    # Ne okuma ne yazma sözcüğü içerir → temkinli "unknown" (otomatik replay edilmez).
    assert d.classify_action("/Sigorta/Sorgula") == "unknown"


# --------------------------------------------------------------------------- #
# is_honeypot
# --------------------------------------------------------------------------- #
def test_honeypot_flags_obfuscated_paths():
    assert d.is_honeypot("/YhXEjw/myMoiXmBymyvoSNgeF") is True
    assert d.is_honeypot("/MX/bKUZRaZbHdvz") is True


def test_honeypot_allows_real_controllers():
    for url in ("/Rapor/Index", "/RadyolojikGoruntu/GetRaporByOrder",
                "/HastaneZiyaret/SonHastaneZiyareti", "/Home/Index"):
        assert d.is_honeypot(url) is False, url


# --------------------------------------------------------------------------- #
# plan_replay — yalnız okuma + bilinen paramlar replay edilir
# --------------------------------------------------------------------------- #
def test_plan_replay_fills_year_params():
    ep = d.Endpoint("/Rapor/Index", "POST", ["startYear", "endYear"], "#tblRaporlarim")
    plan = d.plan_replay(ep, 2020, 2025)
    assert plan.ok is True
    assert plan.data == {"startYear": "2020", "endYear": "2025"}
    assert plan.needs_token_body is False


def test_plan_replay_fills_yili_variant():
    # Hastalik/Patoloji sonu "i" olan varyantı kullanır (canlı keşifte bulundu).
    ep = d.Endpoint("/Hastalik/Index", "POST", ["baslangicYili", "bitisYili"], "#tblHastaliklarim")
    plan = d.plan_replay(ep, 2021, 2026)
    assert plan.ok is True
    assert plan.data == {"baslangicYili": "2021", "bitisYili": "2026"}


def test_plan_replay_get_no_params():
    ep = d.Endpoint("/Home/GetASMBilgileri", "GET", [], "#asm")
    plan = d.plan_replay(ep, 2020, 2025)
    assert plan.ok is True
    assert plan.method == "GET"
    assert plan.data == {}


def test_plan_replay_token_in_body():
    ep = d.Endpoint("/HastaneZiyaret/SonHastaneZiyareti", "POST",
                    ["__RequestVerificationToken"], None)
    plan = d.plan_replay(ep, 2020, 2025)
    assert plan.ok is True
    assert plan.needs_token_body is True


def test_plan_replay_fills_known_enum_param():
    ep = d.Endpoint("/Tahlil/Index", "POST",
                    ["baslangicTarihi", "bitisTarihi", "activeTab"], "#pills-tabContent")
    plan = d.plan_replay(ep, 2020, 2025)
    assert plan.ok is True
    assert plan.data == {"baslangicTarihi": "2020", "bitisTarihi": "2025", "activeTab": "0"}


def test_plan_replay_skips_write():
    ep = d.Endpoint("/Profil/KiloBoyGuncelle", "POST", ["kilo", "boy"], None)
    plan = d.plan_replay(ep, 2020, 2025)
    assert plan.ok is False
    assert "not-read" in plan.reason


def test_plan_replay_skips_unknown_value_params():
    ep = d.Endpoint("/Recete/GetIlacProspektusBilgisi", "POST", ["barcode", "ilacName"], None)
    plan = d.plan_replay(ep, 2020, 2025)
    assert plan.ok is False
    assert "needs-id" in plan.reason


def test_plan_replay_skips_honeypot():
    ep = d.Endpoint("/YhXEjw/myMoiXmBymyvoSNgeF", "GET", [], None)
    plan = d.plan_replay(ep, 2020, 2025)
    assert plan.ok is False
    assert "honeypot" in plan.reason


# --------------------------------------------------------------------------- #
# detect_containers — sunucu-render sayfalar
# --------------------------------------------------------------------------- #
def test_detect_containers_tables_and_cards():
    conts = d.detect_containers(_SERVER_RENDERED)
    assert "#tblRandevuListesi" in conts
    assert ".radyolojiCardListe" in conts


def test_count_rows_in_container():
    assert d.count_rows(_SERVER_RENDERED, "#tblRandevuListesi") == 3


# --------------------------------------------------------------------------- #
# build_report — PHI-güvenli (yalnız API SÖZLEŞMESİ)
# --------------------------------------------------------------------------- #
def _row(**over) -> d.ReportRow:
    """SENTETİK satır — sayılar uydurma.

    Gerçek tarama değerleri KULLANILMAZ: `byte_size`/`row_count` kullanıcının
    verisinin fonksiyonu, yani bir testte de olsa commit'lenirse aynı kardinalite
    sızıntısıdır. (Bu dosya bir ara canlı taramadan kopyalanmış gerçek tahlil/byte
    sayıları taşıyordu — testte de olsa PHI PHI'dir.)
    """
    base = {
        "page": "/Home/Raporlarim", "endpoint": "/Rapor/Index", "method": "POST",
        "param_names": ["startYear", "endYear"], "status": 200, "byte_size": 111111,
        "content_type": "text/html", "container": "#tblRaporlarim", "row_count": 7,
        "verdict": "read",
    }
    return d.ReportRow(**{**base, **over})


def test_build_report_contains_contract_fields():
    report = d.build_report([_row()], meta={"pages_scanned": 1})
    assert "/Rapor/Index" in report
    assert "startYear" in report
    assert "#tblRaporlarim" in report
    assert "read" in report


def test_report_contains_no_user_dependent_quantity():
    """Rapor kullanıcının veri HACMİNDEN bağımsız olmalı — kardinalite de PHI'dir.

    `byte_size` ve `row_count` API sözleşmesinin değil KULLANICININ fonksiyonudur:
    `#tblHastaliklarim | 34` repo sahibinin gerçek tanı sayısıydı ve `fd0b12e`'den
    beri public GitHub'da, üstelik "PHI YOK" başlığının altında duruyordu.

    Bu DAVRANIŞ testi, alan-kümesi kilidinin yapısal olarak yakalayamadığı sınıfı
    yakalar: `row_count` zaten o kümenin içindeydi, yani kilit sonsuza dek yeşil
    kalırken kardinalite akıyordu. Buradaki iddia "şu alan yok" değil, "çıktı veri
    hacminden ETKİLENMİYOR" — kaçış yolu bırakmaz.
    """
    az = d.build_report([_row(byte_size=1000, row_count=1)], meta={"pages_scanned": 1})
    cok = d.build_report([_row(byte_size=999999, row_count=50)], meta={"pages_scanned": 1})
    assert az == cok, "rapor kullanıcının veri hacmine göre değişiyor — kardinalite sızıntısı"


@pytest.mark.parametrize("leak", ["999999", "222222", "42", "7"])
def test_specific_quantities_never_reach_the_report(leak):
    """Regresyon: bu sınıf sayı eskiden rapora yazılıyordu (ve testler ASSERT ediyordu).

    Değerler uydurma — gerçek tarama sayıları burada da kullanılmaz.
    """
    rows = [_row(byte_size=999999, row_count=42), _row(byte_size=222222, row_count=7)]
    assert leak not in d.build_report(rows, meta={})


def test_report_row_carries_no_response_body():
    """`ReportRow`'da gövde taşıyan alan YOKTUR.

    Alan-kümesi kilidi — gövde/önizleme taşıyan bir alan eklenirse fark eder.
    DİKKAT: bu kilit tek başına YETMEZ. `byte_size`/`row_count` bu kümenin
    içindeydi ve yine de PHI sızdırdılar; sızıntı gövde değil KARDİNALİTEYDİ.
    Asıl koruma `test_report_contains_no_user_dependent_quantity`.
    """
    structural = {
        "page", "endpoint", "method", "param_names", "status",
        "byte_size", "content_type", "container", "row_count", "verdict",
    }
    actual = set(d.ReportRow.__dataclass_fields__)
    assert actual == structural, (
        f"ReportRow alanları değişmiş: {actual ^ structural}. Gövde/önizleme taşıyan "
        f"bir alan eklendiyse rapor PHI sızdırabilir."
    )


def test_build_report_renders_no_body_keys():
    """Gövde-benzeri bir anahtar rapora girmemeli."""
    report = d.build_report([_row(container="#accordionTahlil")], meta={})
    assert "/Rapor/Index" in report
    assert "body_preview" not in report
