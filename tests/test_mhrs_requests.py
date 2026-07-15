"""MHRS randevu talebi + "sonuç yok" senaryosu (ağ yok, PHI yok).

Bu dosya **canlı bir kullanıcı senaryosunun** regresyonu: Bursa Şehir Hastanesi /
Nöroloji araması `HTTP 428` + `success: true` + `hastane: []` + `RND4033` uyarısı
döndürüyor. Yani "sonuç yok" ile "hata" birbirine benziyor ve farkı SADECE uyarı
söylüyor.
"""

from __future__ import annotations

import httpx
import pytest

from enabiz_mcp.config import Config
from enabiz_mcp.mhrs.auth import MhrsSession
from enabiz_mcp.tools import mhrs_requests as mr
from enabiz_mcp.tools import mhrs_slots as msl

# Canlı yanıtın GERÇEK şekli (kişiye özel değer yok — kurum/hekim kamuya açık
# katalog verisi olsa da burada uydurma isim kullanılır).
_RND4033 = (
    'Aradığınız kriterlere uygun randevu <font color="#D22929"> <u> <b> '
    "bulunamamıştır.</font></u> </b><br><b> \"Alternatif Hastaneler\" </b> sekmesinden "
    "en erken <b> 30.07.2026 09:50</b> tarihine randevu alabilirsiniz.<br>(RND4033)"
)
_ARAMA_BOS = {
    "lang": "tr-TR",
    "success": True,
    "infos": [],
    "warnings": [{"kodu": "RND4033", "mesaj": _RND4033}],
    "errors": [],
    "data": {
        "hastane": [],
        "semt": [],
        "alternatif": [
            {
                "hekim": {"mhrsHekimId": 457863, "ad": "SENTETİK", "soyad": "HEKİM"},
                "muayeneYeri": {"id": 7082731, "adi": "NÖROLOJİ 1"},
                "kurum": {
                    "mhrsKurumId": 8489,
                    "mhrsAnaKurumId": 0,
                    "kurumAdi": "SENTETİK HASTANE",
                    "ilIlce": {"mhrsIlId": 16, "mhrsIlceId": 1832, "ilceAdi": "OSMANGAZİ"},
                },
                "klinik": {"mhrsKlinikId": 168, "mhrsKlinikAdi": "Nöroloji", "lcetvelTipi": 1},
                "aksiyon": {"id": 200, "aksiyonAdi": "Muayene"},
                "bos": True,
                "bosKapasite": 1,
                "randevuAlinabilir": False,
                "baslangicZamani": "2026-07-30T09:50:00",
            }
        ],
        "semtAramasi": False,
    },
}


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict = {}

    def tool(self, **_kw):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn

        return deco


def _cfg(tmp_path) -> Config:
    return Config(
        tc_kimlik_no=None,
        sifre=None,
        session_path=tmp_path / "session.json",
        min_interval=0.0,
        mhrs_min_interval=0.0,
    )


# --------------------------------------------------------------------------- #
# "Sonuç yok" senaryosu — 428 + uyarı
# --------------------------------------------------------------------------- #
@pytest.fixture
def arama(monkeypatch, tmp_path):
    """Arama tool'unu, canlıdaki 428 + RND4033 yanıtı karşısında kurar."""
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        # MHRS bunu HTTP 428 ile gönderiyor — ama `success: true`.
        return httpx.Response(428, json=_ARAMA_BOS)

    cfg = _cfg(tmp_path)
    monkeypatch.setattr(Config, "from_env", classmethod(lambda _c: cfg))
    monkeypatch.setattr(msl, "mhrs_session", lambda _c, **_k: MhrsSession(jwt="j.w.t", exp=9e9))
    monkeypatch.setattr(
        msl,
        "api_client",
        lambda _c, _j, **_k: httpx.Client(
            base_url="https://prd.mhrs.gov.tr/api/", transport=httpx.MockTransport(handler)
        ),
    )
    fake = _FakeMCP()
    msl.register(fake)
    return fake.tools, sent


def test_http_428_with_success_true_is_not_an_error(arama):
    """MHRS "sonuç yok"u **428** ile gönderir ama `success: true` der.

    428'i başarısızlık sayan bir istemci, sunucunun DÖNDÜĞÜ veriyi (alternatifler)
    ve açıklamayı çöpe atardı.
    """
    tools, _ = arama
    out = tools["enabiz_mhrs_search_institutions"](clinic_id="168", province_id="16")
    assert "error" not in out
    assert out["count"] == 1


def test_rnd4033_warning_reaches_the_model(arama):
    """`RND4033` MUTLAKA çıktıya girmeli — boş sonucu açıklayan tek şey odur.

    `hastane: []` + sessizlik = model "bulunamadı" der ve NEDENİNİ söyleyemez;
    oysa sunucu "alternatif hastaneden en erken 30.07 09:50" diyor.
    """
    tools, _ = arama
    out = tools["enabiz_mhrs_search_institutions"](clinic_id="168", province_id="16")
    kodlar = [n["kodu"] for n in out["notices"]]
    assert "RND4033" in kodlar
    mesaj = next(n["mesaj"] for n in out["notices"] if n["kodu"] == "RND4033")
    assert "30.07.2026 09:50" in mesaj
    assert "<font" not in mesaj and "<b>" not in mesaj, "HTML sökülmemiş"


def test_unbookable_alternative_is_flagged(arama):
    """`randevuAlinabilir: false` taşınmalı — `bos: true` olsa BİLE.

    Canlıda görüldü: alternatif aday `bos: true, bosKapasite: 1` ama
    `randevuAlinabilir: false`. Taşınmazsa model "yer var" sanıp alınamayacak bir
    randevuya yönelir.
    """
    tools, _ = arama
    a = tools["enabiz_mhrs_search_institutions"](clinic_id="168", province_id="16")["candidates"][0]
    assert a["grup"] == "alternatif"
    assert a["bos"] == "True"
    assert a["randevu_alinabilir"] == "False"


def test_district_id_read_from_nested_ililce(arama):
    """İlçe `kurum.ilIlce.mhrsIlceId`'dedir — `kurum.mhrsIlceId` YOKTUR."""
    tools, _ = arama
    a = tools["enabiz_mhrs_search_institutions"](clinic_id="168", province_id="16")["candidates"][0]
    assert a["ilce_id"] == "1832"
    assert a["ilce_adi"] == "OSMANGAZİ"
    assert a["il_id"] == "16"


def test_strip_html_keeps_text_drops_tags():
    assert msl._mesaj("<b>a</b><br>b") == "a b"
    assert msl._mesaj(None) is None
    assert msl._mesaj("<b></b>") is None


# --------------------------------------------------------------------------- #
# Talep tool'ları
# --------------------------------------------------------------------------- #
@pytest.fixture
def talep(monkeypatch, tmp_path):
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.url.path.endswith("/search"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "infos": [],
                    "warnings": [],
                    "errors": [],
                    "data": {
                        "data": [
                            {
                                "id": 987,
                                "kurum": {"kurumAdi": "SENTETİK HASTANE"},
                                "klinik": {"mhrsKlinikAdi": "Nöroloji"},
                                "gecerlilikZamani": "30.08.2026",
                                "randevuTalepDurumu": {"val": 1, "valText": "Bekliyor"},
                                "talepSilinebilir": True,
                                "yenilenebilir": False,
                            }
                        ]
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "success": True,
                "infos": [{"kodu": "GNL1009", "mesaj": "<b>Talebiniz alınmıştır.</b>"}],
                "warnings": [],
                "errors": [],
                "data": None,
            },
        )

    cfg = _cfg(tmp_path)
    monkeypatch.setattr(Config, "from_env", classmethod(lambda _c: cfg))
    monkeypatch.setattr(mr, "mhrs_session", lambda _c, **_k: MhrsSession(jwt="j.w.t", exp=9e9))
    monkeypatch.setattr(
        mr,
        "api_client",
        lambda _c, _j, **_k: httpx.Client(
            base_url="https://prd.mhrs.gov.tr/api/", transport=httpx.MockTransport(handler)
        ),
    )
    fake = _FakeMCP()
    mr.register(fake)
    return fake.tools, sent


def test_create_request_requires_confirm(talep):
    """`confirm=False` talep AÇMAMALI ve hiçbir istek atmamalı."""
    tools, sent = talep
    out = tools["enabiz_mhrs_create_request"](clinic_id="168", institution_id="8489")
    assert out["error"] == "confirm_required"
    assert not sent


def test_create_request_sends_the_browsers_body(talep):
    """Gövde bundle'daki `talepBodyData` ile birebir olmalı."""
    import json

    tools, sent = talep
    out = tools["enabiz_mhrs_create_request"](
        clinic_id="168", institution_id="8489", confirm=True
    )
    assert out["created"] is True
    assert out["message"] == "Talebiniz alınmıştır."  # HTML sökülmüş
    body = json.loads(sent[0].content)
    assert body == {
        "lhatirlatmaSaatSecimi": "1",
        "mhrsHekimId": -1,
        "mhrsKlinikId": 168,
        "mhrsKurumId": 8489,
        "muayeneYeriId": -1,
    }


def test_list_requests_unwraps_double_nested_data(talep):
    """Liste zarfın `data`'sının İÇİNDE bir `data` alanında — bundle `e.data.data.data` okur."""
    tools, _ = talep
    out = tools["enabiz_mhrs_list_requests"]()
    assert out["count"] == 1
    t = out["requests"][0]
    assert t["talep_id"] == "987"
    assert t["kurum"] == "SENTETİK HASTANE"
    assert t["durum"] == "Bekliyor"
    # Sunucunun kararları taşınır — kendi kuralımızı uydurmayız.
    assert t["silinebilir"] == "True"
    assert t["yenilenebilir"] == "False"


def test_delete_request_requires_confirm(talep):
    tools, sent = talep
    assert tools["enabiz_mhrs_delete_request"](request_id="987")["error"] == "confirm_required"
    assert not sent


def test_delete_request_with_confirm_calls_endpoint(talep):
    tools, sent = talep
    out = tools["enabiz_mhrs_delete_request"](request_id="987", confirm=True)
    assert out["deleted"] is True
    assert [r for r in sent if r.method == "DELETE" and r.url.path.endswith("/987")]


def test_request_paths_are_classified_write():
    """Talep oluştur/sil YAZMA sınıfında olmalı — `allow_write` gerçekten gerekli."""
    from enabiz_mcp.mhrs.discovery import classify_mhrs_call

    assert classify_mhrs_call("POST", mr.TALEP_PATH) == "write"
    assert classify_mhrs_call("DELETE", mr.TALEP_DELETE_PATH.format(talep_id="1")) == "write"
    assert classify_mhrs_call("GET", mr.TALEP_SEARCH_PATH) == "read"
