"""Config: kimlik doğrulama bayrağı ve env float ayrıştırma."""

from enabiz_mcp.config import Config, _env_float


def _cfg(tmp_path, tc, sifre):
    return Config(tc_kimlik_no=tc, sifre=sifre, session_path=tmp_path / "s.json")


def test_credentials_configured(tmp_path):
    assert _cfg(tmp_path, "1", "2").credentials_configured
    assert not _cfg(tmp_path, None, None).credentials_configured
    assert not _cfg(tmp_path, "1", None).credentials_configured


def test_env_float_valid(monkeypatch):
    monkeypatch.setenv("ENABIZ_X", "1.5")
    assert _env_float("ENABIZ_X", 0.5) == 1.5


def test_env_float_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("ENABIZ_X", "abc")
    assert _env_float("ENABIZ_X", 0.5) == 0.5


def test_env_float_missing_falls_back(monkeypatch):
    monkeypatch.delenv("ENABIZ_X", raising=False)
    assert _env_float("ENABIZ_X", 0.5) == 0.5
