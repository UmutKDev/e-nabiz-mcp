"""Yapılandırma: kimlik bilgileri (env) ve oturum önbellek yolu.

Kimlik bilgileri YALNIZCA ortam değişkenlerinden (veya `.env`) okunur; asla kod
içine gömülmez ve MCP tool argümanı olarak taşınmaz.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # .env varsa yükle (opsiyonel bağımlılık, fastmcp ile birlikte gelir)
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv yoksa sessizce geç
    pass

BASE_URL = "https://enabiz.gov.tr"


def _env_float(name: str, default: float) -> float:
    """Ortam değişkenini float'a çevirir; geçersizse varsayılanı döndürür."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _default_session_path() -> Path:
    """Oturum önbelleği için yerel, kullanıcıya özel varsayılan yol."""
    override = os.environ.get("ENABIZ_SESSION_PATH")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "enabiz-mcp" / "session.json"


def _default_download_dir() -> Path:
    """İndirilen PDF/dosyalar için yerel, kullanıcıya özel varsayılan dizin."""
    override = os.environ.get("ENABIZ_DOWNLOAD_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "enabiz-mcp" / "downloads"


@dataclass(frozen=True)
class Config:
    """Çalışma zamanı yapılandırması."""

    tc_kimlik_no: str | None
    sifre: str | None
    session_path: Path
    download_dir: Path = field(default_factory=_default_download_dir)
    base_url: str = BASE_URL
    # Portalın WAF'ını (SAGLIK* cookie) tetiklememek için istekler arası minimum
    # bekleme (saniye). ENABIZ_MIN_INTERVAL ile ayarlanır.
    min_interval: float = 0.5
    # Nazik hız sınırı / gerçekçi tarayıcı taklidi için varsayılan User-Agent.
    user_agent: str = field(
        default=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        )
    )

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            tc_kimlik_no=os.environ.get("ENABIZ_TCKIMLIK"),
            sifre=os.environ.get("ENABIZ_SIFRE"),
            session_path=_default_session_path(),
            download_dir=_default_download_dir(),
            min_interval=_env_float("ENABIZ_MIN_INTERVAL", 0.5),
        )

    @property
    def credentials_configured(self) -> bool:
        return bool(self.tc_kimlik_no and self.sifre)
