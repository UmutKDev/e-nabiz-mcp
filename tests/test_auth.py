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
