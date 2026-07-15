"""Oturum kalıcılığı ve kimlik-koruma testleri (ağ yok)."""

import stat

import httpx
import pytest

from enabiz_mcp import auth
from enabiz_mcp.config import Config
from enabiz_mcp.tools._common import auth_guarded


def _cfg(tmp_path):
    return Config(tc_kimlik_no="123", sifre="x", session_path=tmp_path / "session.json")


def test_session_roundtrip_and_permissions(tmp_path):
    cfg = _cfg(tmp_path)
    jar = httpx.Cookies()
    jar.set(".EnabizSESSIONID", "abc", domain="enabiz.gov.tr", path="/")
    auth.save_session(cfg, jar)

    loaded = auth.load_session(cfg)
    assert loaded is not None
    assert auth.has_auth_cookie(loaded)
    # Gizlilik: oturum dosyası yalnızca sahibe okunur/yazılır (chmod 600).
    assert stat.S_IMODE(cfg.session_path.stat().st_mode) == 0o600


def test_has_auth_cookie_false_for_non_auth_cookies():
    jar = httpx.Cookies()
    jar.set("SAGLIK014b2321", "x", domain="enabiz.gov.tr", path="/")
    assert not auth.has_auth_cookie(jar)


def test_load_session_missing_returns_none(tmp_path):
    assert auth.load_session(_cfg(tmp_path)) is None


def test_authed_client_raises_without_session(tmp_path):
    with pytest.raises(auth.AuthRequired):
        auth.authed_client(_cfg(tmp_path))


def test_auth_guarded_converts_authrequired():
    @auth_guarded
    def boom() -> dict:
        raise auth.AuthRequired("düştü")

    out = boom()
    assert out["error"] == "auth_required"
    assert "düştü" in out["message"]
    assert "hint" in out


def test_auth_guarded_passes_through_success():
    @auth_guarded
    def ok() -> dict:
        return {"ok": True}

    assert ok() == {"ok": True}


# --------------------------------------------------------------------------- #
# MHRS hataları — `except` SIRASI davranıştır
# --------------------------------------------------------------------------- #
def test_auth_guarded_rate_limited_is_not_swallowed_by_mhrs_error():
    """RNDS1000 `rate_limited` dönmeli — `mhrs_error` DEĞİL.

    `MhrsRateLimited` bir `MhrsError` alt sınıfıdır; `except MhrsError` önce
    yazılırsa RNDS1000 onun içine düşer ve "TEKRAR DENEMEYİN" ipucu SESSİZCE
    kaybolur. Model o ipucu olmadan kilidi geçici hata sanıp döngüye girer — ve
    döngü kullanıcıyı online randevudan tamamen çıkarır. Bu test o sırayı kilitler.
    """
    from enabiz_mcp.mhrs.auth import MhrsRateLimited

    @auth_guarded
    def boom() -> dict:
        raise MhrsRateLimited("çok fazla sorgu", "RNDS1000")

    out = boom()
    assert out["error"] == "rate_limited"
    assert out["kodu"] == "RNDS1000"
    assert "TEKRAR DENEMEYİN" in out["hint"]


def test_auth_guarded_mhrs_auth_required_is_not_swallowed_by_mhrs_error():
    """LGN1004/LGN2001 `auth_required` dönmeli — aynı alt-sınıf tuzağı."""
    from enabiz_mcp.mhrs.auth import MhrsAuthRequired

    @auth_guarded
    def boom() -> dict:
        raise MhrsAuthRequired("oturum yok", "LGN1004")

    out = boom()
    assert out["error"] == "auth_required"
    assert out["kodu"] == "LGN1004"


def test_auth_guarded_drops_dead_jwt_so_next_call_can_recover(tmp_path, monkeypatch):
    """`MhrsAuthRequired` kayıtlı JWT'yi SİLMELİ — ipucunun doğru olmasının şartı.

    CANLIDA ölçülen sorun: `mhrs_session` canlılığı yalnız yerel `exp` ile ölçüyor ve
    `exp` güvenilir değil — JWT yerel olarak 19.6 saat geçerli görünürken sunucu 401
    verdi (sebep: kullanıcı tarayıcıdan MHRS'ye girmiş, MHRS tek oturum tutuyor).

    Silme olmasa cache ölü token'ı sonsuza dek servis eder: `exp` geçmediği için
    `mhrs_session` aynı ölü JWT'yi döndürür, her çağrı 401 alır, hiçbir şey
    kendiliğinden düzelmez — ve "bir sonraki çağrı zinciri yeniden koşturur" ipucu
    bir YALAN olur.
    """
    from enabiz_mcp.config import Config
    from enabiz_mcp.mhrs import auth as mhrs_auth
    from enabiz_mcp.mhrs.auth import MhrsAuthRequired, MhrsSession

    cfg = Config(
        tc_kimlik_no=None,
        sifre=None,
        session_path=tmp_path / "session.json",
        min_interval=0.0,
        mhrs_min_interval=0.0,
    )
    monkeypatch.setattr(Config, "from_env", classmethod(lambda _c: cfg))
    mhrs_auth.save_mhrs_session(cfg, MhrsSession(jwt="olu.jwt.imza", exp=9e9))
    assert mhrs_auth.load_mhrs_session(cfg) is not None  # önce VAR

    @auth_guarded
    def boom() -> dict:
        raise MhrsAuthRequired("MHRS oturumu reddedildi (HTTP 401).", None)

    out = boom()
    assert out["error"] == "auth_required"
    assert mhrs_auth.load_mhrs_session(cfg) is None, "ölü JWT cache'te kaldı"


def test_auth_guarded_drop_keeps_enabiz_cookies(tmp_path, monkeypatch):
    """MHRS token'ı silinirken e-Nabız cookie'leri HAYATTA kalmalı — ortak dosya."""
    from enabiz_mcp import auth as enabiz_auth
    from enabiz_mcp.config import Config
    from enabiz_mcp.mhrs import auth as mhrs_auth
    from enabiz_mcp.mhrs.auth import MhrsAuthRequired, MhrsSession

    cfg = Config(
        tc_kimlik_no=None,
        sifre=None,
        session_path=tmp_path / "session.json",
        min_interval=0.0,
        mhrs_min_interval=0.0,
    )
    monkeypatch.setattr(Config, "from_env", classmethod(lambda _c: cfg))
    enabiz_auth.write_session_file(cfg, {"cookies": [{"name": "x", "value": "y"}]})
    mhrs_auth.save_mhrs_session(cfg, MhrsSession(jwt="olu.jwt.imza", exp=9e9))

    @auth_guarded
    def boom() -> dict:
        raise MhrsAuthRequired("401", None)

    boom()
    assert mhrs_auth.load_mhrs_session(cfg) is None
    assert enabiz_auth.read_session_file(cfg).get("cookies"), "e-Nabız cookie'leri silindi!"


def test_auth_guarded_generic_mhrs_error_keeps_code():
    """Sınıflanamayan MHRS hatası kodu MODELE taşımalı — 'bilinmeyen hata' demesin."""
    from enabiz_mcp.mhrs.auth import MhrsError

    @auth_guarded
    def boom() -> dict:
        raise MhrsError("slot dolmuş", "RND4105")

    out = boom()
    assert out["error"] == "mhrs_error"
    assert out["kodu"] == "RND4105"
