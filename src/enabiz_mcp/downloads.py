"""PDF/dosya indirme yardımcısı — salt-okunur (uzaktan getirir, yerel diske yazar).

İndirilen dosyalar `ENABIZ_DOWNLOAD_DIR`'e (chmod 600) yazılır. PDF tool'ları dosya
içeriğini LLM bağlamına sokmadan yalnız metadata döner: `{saved_path, byte_size,
sha256, content_type}`. Böylece PHI kullanıcının diskinde kalır, transkripte girmez.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def _safe_name(name: str) -> str:
    """Dosya adını güvenli karakterlere indirger (yol ayracı/özel karakter yok)."""
    cleaned = _UNSAFE.sub("_", name).strip("_")[:120]
    return cleaned or "download"


def save_download(
    content: bytes, filename: str, download_dir: Path, content_type: str = "application/pdf"
) -> dict:
    """`content` baytlarını `download_dir/filename`'e yazar; PHI-güvenli metadata döner."""
    download_dir.mkdir(parents=True, exist_ok=True)
    path = download_dir / _safe_name(filename)
    path.write_bytes(content)
    path.chmod(0o600)
    return {
        "saved_path": str(path),
        "byte_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "content_type": content_type,
    }
