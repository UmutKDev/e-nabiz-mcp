"""MHRS randevu YAZMA tool'ları — iki adımlı onay (ağ yok, PHI yok).

Bu dosyanın koruduğu tek şey: **modelin uydurduğu bir slot id ile kullanıcıya
randevu yazılamaması.** Yanlış randevunun bedeli gerçek — randevusuna gitmeyen ve
iptal etmeyen kişi aynı branştan 15 gün randevu alamaz (saglik.gov.tr TR,94138).
"""

from __future__ import annotations

import httpx
import pytest

from enabiz_mcp.config import Config
from enabiz_mcp.mhrs.auth import MhrsSession
from enabiz_mcp.mhrs.discovery import classify_mhrs_call
from enabiz_mcp.tools import mhrs_booking as mb
from enabiz_mcp.tools import mhrs_slots as msl


def _env(data) -> dict:
    return {"lang": "tr", "success": True, "infos": [], "warnings": [], "errors": [], "data": data}


_SLOT_INFO = {
    "slot": {
        "id": 555001,
        "fkCetvelId": 777,
        "baslangicZamani": "2030-01-01T09:00:00",
        "bitisZamani": "2030-01-01T09:10:00",
    },
    "muayeneYeri": {"id": 42, "adi": "SENTETİK Poliklinik"},
    "klinik": {"mhrsKlinikAdi": "Göz", "lcetvelTipi": 1},
    "kurum": {"anaKurumAdi": "SENTETİK Hastane"},
    "randevuBaslangicZamaniStr": {"tarih": "01.01.2030", "gun": "Salı", "saat": "09:00"},
    "randevuBitisZamaniStr": {"saat": "09:10"},
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
def booking(monkeypatch, tmp_path):
    """Randevu tool'larını sentetik MHRS karşısında kurar; giden istekleri kaydeder."""
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.url.path.endswith("randevu-bilgileri"):
            return httpx.Response(200, json=_env(_SLOT_INFO))
        if request.url.path.endswith("randevu-ekle"):
            return httpx.Response(200, json=_env({"hastaRandevuNumarasi": "12345678"}))
        return httpx.Response(200, json=_env({}))

    cfg = Config(
        tc_kimlik_no=None,
        sifre=None,
        session_path=tmp_path / "session.json",
        min_interval=0.0,
        mhrs_min_interval=0.0,
    )
    monkeypatch.setattr(Config, "from_env", classmethod(lambda _cls: cfg))
    monkeypatch.setattr(mb, "mhrs_session", lambda _c, **_k: MhrsSession(jwt="j.w.t", exp=9e9))

    def fake_api_client(_cfg, _jwt, **_kw):
        return httpx.Client(
            base_url="https://prd.mhrs.gov.tr/api/", transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(mb, "api_client", fake_api_client)
    mb._PENDING.clear()
    fake = _FakeMCP()
    mb.register(fake)
    return fake.tools, sent


# --------------------------------------------------------------------------- #
# İki adımlı onayın ÇEKİRDEĞİ
# --------------------------------------------------------------------------- #
def test_book_confirm_rejects_forged_token(booking):
    """Uydurma token randevu ALMAMALI — bu dosyanın var oluş sebebi.

    Model bir `confirm_token` uydurursa randevu alınmamalı ve `randevu-ekle`'ye
    HİÇBİR istek gitmemeli.
    """
    tools, sent = booking
    out = tools["enabiz_mhrs_book_confirm"](confirm_token="uydurma-token-123")
    assert out["error"] == "invalid_token"
    assert not [r for r in sent if "randevu-ekle" in str(r.url)], "yazma isteği gitti!"


def test_book_prepare_writes_nothing_to_randevu_ekle(booking):
    """`book_prepare` randevu ALMAZ — yalnız slotu doğrular."""
    tools, sent = booking
    out = tools["enabiz_mhrs_book_prepare"](slot_id="555001")
    assert "confirm_token" in out
    assert not [r for r in sent if "randevu-ekle" in str(r.url)]


def test_book_confirm_body_comes_from_server_not_from_the_model(booking):
    """Randevu gövdesi SUNUCUNUN doğruladığı slottan kurulur, tool argümanından değil.

    Model `slot_id` uydursa bile gövdedeki `fkSlotId`/`fkCetvelId`/zamanlar sunucunun
    `randevu-bilgileri` yanıtından gelir — uydurulmuş bir gövde MHRS'ye gidemez.
    """
    tools, sent = booking
    token = tools["enabiz_mhrs_book_prepare"](slot_id="555001")["confirm_token"]
    out = tools["enabiz_mhrs_book_confirm"](confirm_token=token)
    assert out["booked"] is True and out["hrn"] == "12345678"

    import json

    ekle = [r for r in sent if "randevu-ekle" in str(r.url)]
    assert len(ekle) == 1
    body = json.loads(ekle[0].content)
    assert body["fkSlotId"] == 555001  # sunucudan
    assert body["fkCetvelId"] == 777  # sunucudan
    assert body["baslangicZamani"] == "2030-01-01T09:00:00"


def test_confirm_token_is_single_use(booking):
    """Token bir kez kullanılır — aynı token'la ikinci randevu alınamaz."""
    tools, sent = booking
    token = tools["enabiz_mhrs_book_prepare"](slot_id="555001")["confirm_token"]
    assert tools["enabiz_mhrs_book_confirm"](confirm_token=token)["booked"] is True
    again = tools["enabiz_mhrs_book_confirm"](confirm_token=token)
    assert again["error"] == "invalid_token"
    assert len([r for r in sent if "randevu-ekle" in str(r.url)]) == 1


def test_book_prepare_refuses_when_slot_has_no_cetvel(booking, monkeypatch):
    """Slot doğrulanamazsa token ÜRETİLMEZ — dolmuş slot için randevu denenmez."""
    tools, _ = booking

    def bad(_cfg, _jwt, **_kw):
        return httpx.Client(
            base_url="https://prd.mhrs.gov.tr/api/",
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=_env({"slot": {}}))),
        )

    monkeypatch.setattr(mb, "api_client", bad)
    out = tools["enabiz_mhrs_book_prepare"](slot_id="555001")
    assert out["error"] == "mhrs_error"
    assert "confirm_token" not in out
    assert not mb._PENDING


def test_cancel_requires_explicit_confirm(booking):
    """`confirm=False` iptal ETMEMELİ ve hiçbir istek atmamalı."""
    tools, sent = booking
    out = tools["enabiz_mhrs_cancel"](hrn="12345678")
    assert out["error"] == "confirm_required"
    assert not [r for r in sent if "iptal-et" in str(r.url)]


def test_cancel_with_confirm_calls_the_endpoint(booking):
    tools, sent = booking
    out = tools["enabiz_mhrs_cancel"](hrn="12345678", confirm=True)
    assert out["cancelled"] is True
    assert [r for r in sent if "iptal-et/12345678" in str(r.url)]


def test_cancel_prepare_releases_the_lock_and_drops_token(booking):
    """Vazgeçme kilidi bırakmalı — `randevu-bilgileri` slotu kilitliyor olabilir."""
    tools, sent = booking
    token = tools["enabiz_mhrs_book_prepare"](slot_id="555001")["confirm_token"]
    out = tools["enabiz_mhrs_book_cancel_prepare"](confirm_token=token)
    assert out["released"] is True and out["token_vardi"] is True
    assert token not in mb._PENDING
    assert [r for r in sent if r.method == "DELETE" and "slot-kilitleme" in str(r.url)]


# --------------------------------------------------------------------------- #
# Yazma kapısı — sınıflandırıcı ile tutarlılık
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", mb.BOOK_PATH),
        ("DELETE", mb.UNLOCK_PATH),
        ("GET", mb.CANCEL_PATH.format(hrn="1")),
    ],
)
def test_booking_paths_are_classified_write(method, path):
    """Randevu uçları YAZMA sınıfında olmalı — `allow_write=True` gerçekten gerekli.

    `iptal-et` GET'tir ama yazmadır: sınıflama ad-bazlı olmasaydı bu uç "okuma"
    sayılır ve kapı hiç devreye girmezdi.
    """
    assert classify_mhrs_call(method, path) == "write"


@pytest.mark.parametrize("path", [msl.ARAMA_PATH, msl.SLOT_PATH])
def test_slot_search_paths_are_classified_read(path):
    """Arama/slot POST'tur ama OKUMA — aksi hâlde kendi kapımız Faz 2b'yi bloklardı."""
    assert classify_mhrs_call("POST", path) == "read"


# --------------------------------------------------------------------------- #
# Slot ağacı — CANLI yakalanan derinlik hatası
# --------------------------------------------------------------------------- #
#: Canlı yanıtın GERÇEK şekli (sentetik değerlerle). Kritik nokta: `saatSlotList[]`
#: bir SAAT GRUBUdur, slot DEĞİL — asıl slotlar onun `slotList[]`'indedir.
_GUN_RAW = {
    "gun": "2030-01-01",
    "hekimSlotList": [
        {
            "hekim": {"ad": "AYŞE", "soyad": "YILMAZ", "mhrsHekimId": 1234},
            "klinik": {"lcetvelTipi": 1},
            "muayeneYeriSlotList": [
                {
                    "muayeneYeri": {"adi": "SENTETİK Pol. 1"},
                    "saatSlotList": [
                        {
                            "saat": "09:00:00",
                            "saatStr": "09:00",
                            "bos": True,
                            "slotList": [
                                {
                                    "id": 111,
                                    "bos": True,
                                    "ek": False,
                                    "isKurali": False,
                                    "slot": {"id": 111},
                                    "baslangicZamanStr": {"saat": "09:00", "tarih": "01.01.2030"},
                                },
                                {
                                    "id": 112,
                                    "bos": False,
                                    "ek": False,
                                    "isKurali": False,
                                    "slot": {"id": 112},
                                    "baslangicZamanStr": {"saat": "09:15", "tarih": "01.01.2030"},
                                },
                            ],
                        }
                    ],
                    "saatSlotListEk": [],
                }
            ],
        }
    ],
}


def test_gun_descends_into_slotlist_not_saatslotlist():
    """Slotlar `saatSlotList[].slotList[]` içindedir — bir kat DAHA derin.

    CANLIDA yakalanan hata: parser `saatSlotList` girdilerinde `.slot` arıyordu; orada
    yok, bir alt katta. Sonuç: her slot eleniyor ve "0 boş saat" görünüyordu — yani
    DOLU bir hastane ile BOZUK bir parser ayırt edilemez hâle gelmişti. Gerçekte o
    aramada 135 ve 322 alınabilir slot vardı.
    """
    g = msl._gun(_GUN_RAW)
    saatler = g["hekimler"][0]["saatler"]
    assert [s["slot_id"] for s in saatler] == ["111", "112"]
    assert saatler[0]["saat"] == "09:00"
    assert saatler[0]["bos"] == "True"
    assert saatler[1]["bos"] == "False"


def test_gun_keeps_hekim_and_muayene_yeri():
    g = msl._gun(_GUN_RAW)
    assert g["hekimler"][0]["hekim"] == "AYŞE YILMAZ"
    assert g["hekimler"][0]["saatler"][0]["muayene_yeri"] == "SENTETİK Pol. 1"


def test_gun_returns_empty_on_unexpected_shape():
    assert msl._gun({"gun": "2030-01-01"})["hekimler"] == []
    assert msl._gun(None) is None
    assert msl._gun({"hekimSlotList": []}) is None  # `gun` yoksa gün değildir


def test_slot_id_helper_keeps_zero_distinct_from_sentinel():
    """`0` sentinel'e (`-1`) düşmemeli — MHRS'nin kendi bundle'ındaki hata bu."""
    assert msl._id("0") == 0
    assert msl._id(None) == msl.ANY_ID
    assert msl._id("") == msl.ANY_ID
    assert msl._id("çöp") == msl.ANY_ID
