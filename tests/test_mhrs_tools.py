"""MHRS okuma tool'ları — lookup ve randevu listeleri (ağ yok, PHI yok).

En kritik iki sınıf:

1. **İki yanıt şekli.** MHRS bazı uçlarda ZARF (`{success, data}`), bazılarında
   ÇIPLAK DİZİ döner ve bu uca göre değişir, prefix'e göre DEĞİL. Çıplak şekli
   reddeden bir `unwrap` ilçe/lookup uçlarını tamamen kullanılamaz yapar.

2. **Boş sonuç > sessiz yanlış-eşleme** (invaryant #2). Beklenmedik şekilde `[]`
   döner; uydurma kayıt üretilmez.
"""

from __future__ import annotations

import httpx
import pytest

from enabiz_mcp.mhrs.client import unwrap
from enabiz_mcp.tools import mhrs_appointments as ma
from enabiz_mcp.tools import mhrs_search as ms


def _env(data) -> dict:
    """MHRS başarı zarfı."""
    return {"lang": "tr", "success": True, "infos": [], "warnings": [], "errors": [], "data": data}


# --------------------------------------------------------------------------- #
# İki yanıt şekli — `unwrap`
# --------------------------------------------------------------------------- #
def test_unwrap_accepts_bare_list_response():
    """Çıplak dizi yanıtı kabul edilmeli — `ilce/selectinput` ve lookup'lar böyle.

    Regresyon: `unwrap` gövdenin dict olmasını şart koşuyordu ve çıplak uçlarda
    "MHRS beklenen zarfı döndürmedi" ile patlıyordu. Bundle kanıtı: istemci bu
    uçlarda gövdeyi doğrudan dizi gibi kullanıyor (`e.data.map(...)`,
    `Object.assign([], e.data)`), zarfa hiç inmiyor.
    """
    body = [{"value": 1, "text": "Merkez"}, {"value": 2, "text": "Kuzey"}]
    assert unwrap(httpx.Response(200, json=body)) == body


def test_unwrap_still_opens_envelope():
    """Zarflı uçlar (`kurum/...`) bozulmadı."""
    assert unwrap(httpx.Response(200, json=_env({"a": 1}))) == {"a": 1}


def test_unwrap_envelope_with_list_data_returns_the_list():
    """Zarf içinde dizi varsa dizi döner — `{"data": [...]}` sarmalanmaz.

    Eski davranış listeyi `{"data": [...]}` içine sarıyordu; çağıran zarflı ve
    çıplak uçlar için iki farklı açma kodu yazmak zorunda kalırdı.
    """
    assert unwrap(httpx.Response(200, json=_env([{"value": 1}]))) == [{"value": 1}]


# --------------------------------------------------------------------------- #
# Lookup düğümleri
# --------------------------------------------------------------------------- #
def test_node_keeps_ids_as_strings():
    """`value` bir id gibi görünse de `str` kalır — ev kuralı.

    MHRS `-1` sentinel'ini, `0`ı ve gerçek id'leri AYNI alanda taşıyor. Sayıya
    çevirmek `0`ı falsy yapıp sentinel mantığını bozan hatadır; MHRS kendi
    bundle'ında bunu elle telafi etmek zorunda kalmış
    (`mhrsHekimId: 0 !== e.mhrsHekimId ? e.mhrsHekimId : -1`).
    """
    n = ms._node({"value": 0, "text": "Sıfır"})
    assert n["id"] == "0" and isinstance(n["id"], str)
    assert ms._node({"value": -1, "text": "Farketmez"})["id"] == "-1"


def test_node_maps_value2_value3_to_meaningful_names():
    """`value2`/`value3` bundle'da `favori`/`cetvelTipi` olarak parse ediliyor."""
    n = ms._node({"value": 6, "text": "Ankara", "value2": 1, "value3": 2})
    assert n["favori_kodu"] == "1"
    assert n["cetvel_tipi"] == "2"


def test_node_recurses_into_children():
    raw = {"value": 6, "text": "Ankara", "children": [{"value": 61, "text": "Çankaya"}]}
    n = ms._node(raw)
    assert n["children"] == [{"id": "61", "name": "Çankaya"}]


def test_nodes_returns_empty_on_unexpected_shape():
    """Beklenmedik şekil → `[]`; uydurma liste DEĞİL (invaryant #2)."""
    assert ms._nodes({"success": True}) == []
    assert ms._nodes(None) == []
    assert ms._nodes(["düz string", 42]) == []


def test_node_drops_entry_without_text_and_value():
    assert ms._node({"foo": "bar"}) is None


# --------------------------------------------------------------------------- #
# Randevu DTO'ları
# --------------------------------------------------------------------------- #
def _randevu(**over) -> dict:
    raw = {
        "hastaRandevuNumarasi": "12345678",
        "kurumAdi": "SENTETİK Hastane",
        "mhrsKlinikAdi": "Göz",
        "randevuBaslangicZamaniStr": {"tarih": "01.01.2030", "gun": "Salı", "saat": "09:00"},
        "randevuBitisZamaniStr": {"saat": "09:10"},
        "randevuKayitDurumu": {"val": 1, "valText": "Aktif"},
    }
    raw.update(over)
    return raw


def test_appointment_requires_hrn():
    """`hrn` yoksa kayıt randevu DEĞİL — iptal edilemez, listelenmez."""
    assert ma._appointment({"kurumAdi": "X"}) is None
    assert ma._appointment(_randevu())["hrn"] == "12345678"


def test_appointment_flattens_server_formatted_time():
    """Sunucunun parçalanmış zamanı taşınır — kendi tarih tahminimiz değil."""
    a = ma._appointment(_randevu())
    assert a["baslangic"] == {"tarih": "01.01.2030", "gun": "Salı", "saat": "09:00"}
    assert a["bitis"] == {"saat": "09:10"}


def test_appointment_takes_status_text_not_code():
    a = ma._appointment(_randevu())
    assert a["kayit_durumu"] == "Aktif"


def test_appointment_values_are_all_strings():
    """Hiçbir değer int/bool'a çevrilmez — ev kuralı."""
    a = ma._appointment(_randevu(ek=False, shmMi=True))
    for key in ("hrn", "ek_slot", "shm_mi"):
        assert isinstance(a[key], str), key


def test_bucket_returns_empty_on_unexpected_shape():
    assert ma._bucket(None, "aktifRandevuDtoList") == []
    assert ma._bucket({"baska": []}, "aktifRandevuDtoList") == []


def test_bucket_skips_malformed_rows_but_keeps_good_ones():
    """Bozuk satır listeyi çökertmez; iyi olanlar korunur."""
    data = {"aktifRandevuDtoList": [{"kurumAdi": "hrn yok"}, _randevu()]}
    out = ma._bucket(data, "aktifRandevuDtoList")
    assert [a["hrn"] for a in out] == ["12345678"]


# --------------------------------------------------------------------------- #
# Uçtan uca — sentetik MHRS karşısında
# --------------------------------------------------------------------------- #
#: Uç → sentetik yanıt. İl/ilçe ÇIPLAK dizi, kurum/... ZARFLI — canlı build'deki
#: ayrımın aynısı; smoke test bu farkı da sınar.
_ROUTES: dict = {
    "/api/" + ms.IL_PATH: [{"value": 6, "text": "SENTETİK İl", "value2": 1, "value3": 2}],
    "/api/" + ms.ILCE_PATH.format(il_id="6"): [{"value": 61, "text": "SENTETİK İlçe"}],
    "/api/" + ms.KLINIK_PATH: _env([{"value": 9, "text": "SENTETİK Klinik"}]),
    "/api/" + ma.UPCOMING_PATH: _env({"aktifRandevuDtoList": [_randevu()]}),
    "/api/" + ma.HISTORY_PATH: _env(
        {
            "gecmisRandevuDtoList": [_randevu(hastaRandevuNumarasi="999")],
            "gizliRandevuGecmisiDtoList": [_randevu(hastaRandevuNumarasi="777")],
        }
    ),
}


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict = {}

    def tool(self, **_kw):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn

        return deco


@pytest.fixture
def mhrs_tools(monkeypatch, tmp_path):
    """MHRS tool'larını sentetik bir API karşısında kurar — AĞ YOK, SSO zinciri YOK."""
    from enabiz_mcp.config import Config
    from enabiz_mcp.mhrs.auth import MhrsSession

    def handler(request: httpx.Request) -> httpx.Response:
        body = _ROUTES.get(request.url.path)
        if body is None:
            return httpx.Response(404, json={"success": False, "errors": [{"kodu": "YOK"}]})
        return httpx.Response(200, json=body)

    cfg = Config(
        tc_kimlik_no=None,
        sifre=None,
        session_path=tmp_path / "session.json",
        min_interval=0.0,
        mhrs_min_interval=0.0,
    )
    monkeypatch.setattr(Config, "from_env", classmethod(lambda _cls: cfg))
    fake_session = MhrsSession(jwt="sentetik.jwt.imza", exp=9e9)

    def fake_api_client(_cfg, _jwt, **_kw):
        return httpx.Client(
            base_url="https://prd.mhrs.gov.tr/api/", transport=httpx.MockTransport(handler)
        )

    for mod in (ms, ma):
        monkeypatch.setattr(mod, "mhrs_session", lambda _cfg, **_k: fake_session)
        monkeypatch.setattr(mod, "api_client", fake_api_client)

    fake = _FakeMCP()
    ms.register(fake)
    ma.register(fake)
    return fake.tools


#: Zorunlu argümanı olan tool'lar. Argümansız çağrılabilenler boş dict alır.
_TOOL_ARGS: dict = {"enabiz_mhrs_list_districts": {"province_id": "6"}}


def test_every_mhrs_tool_is_callable(mhrs_tools):
    """Beş tool da çağrılabilmeli — `error` DÖNMEMELİ.

    İki-dosya tuzağının ve import hatalarının canlıda değil burada patlaması için.
    """
    assert len(mhrs_tools) == 5, sorted(mhrs_tools)
    for name, fn in mhrs_tools.items():
        out = fn(**_TOOL_ARGS.get(name, {}))
        assert isinstance(out, dict), name
        assert "error" not in out, f"{name} → {out}"


def test_lookup_tools_parse_both_response_shapes(mhrs_tools):
    """İl ÇIPLAK dizi, klinik ZARFLI — ikisi de aynı şekilde parse edilmeli."""
    prov = mhrs_tools["enabiz_mhrs_list_provinces"]()
    assert prov["provinces"] == [
        {"id": "6", "name": "SENTETİK İl", "favori_kodu": "1", "cetvel_tipi": "2"}
    ]
    clin = mhrs_tools["enabiz_mhrs_list_clinics"]()
    assert clin["clinics"] == [{"id": "9", "name": "SENTETİK Klinik"}]


def test_districts_tool_passes_province_id_into_path(mhrs_tools):
    out = mhrs_tools["enabiz_mhrs_list_districts"](province_id="6")
    assert out["districts"] == [{"id": "61", "name": "SENTETİK İlçe"}]
    assert out["province_id"] == "6"


def test_upcoming_returns_hrn(mhrs_tools):
    """`hrn` iptalin anahtarı ve e-Nabız HTML tablosunda YOK — bu modülün varlık sebebi."""
    out = mhrs_tools["enabiz_mhrs_list_upcoming"]()
    assert [a["hrn"] for a in out["appointments"]] == ["12345678"]


def test_history_reports_hidden_only_as_a_count(mhrs_tools):
    """Gizlenmiş randevuların İÇERİĞİ modele açılmamalı — kullanıcı onları kasten gizledi.

    Yalnız sayısı bildirilir; içerik dönerse kullanıcının gizleme kararı sessizce
    geri alınmış olur.
    """
    out = mhrs_tools["enabiz_mhrs_list_history"]()
    assert out["hidden_count"] == 1
    assert [a["hrn"] for a in out["appointments"]] == ["999"]
    assert "777" not in str(out), "gizli randevu içeriği sızdı"


@pytest.mark.parametrize(
    "path",
    [
        ms.IL_PATH,
        ms.KLINIK_PATH,
        ma.UPCOMING_PATH,
        ma.HISTORY_PATH,
        ms.ILCE_PATH.format(il_id="6"),
    ],
)
def test_tool_paths_are_classified_read(path):
    """Faz 2'nin HİÇBİR ucu yazma sınıfında olmamalı.

    `_forbid_write` çalışma-zamanı kapısı `classify_mhrs_call`'a dayanır; bir tool
    yolu yanlışlıkla yazma sınıfına düşerse tool canlıda `WriteNotAllowed` ile
    patlar. Bu tam olarak `slot-sorgulama`'da yaşandı.
    """
    from enabiz_mcp.mhrs.discovery import classify_mhrs_call

    assert classify_mhrs_call("GET", path) == "read"
