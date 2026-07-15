"""İndirme yardımcısı testleri (ağ yok; tmp dizine yazar)."""

import hashlib
import stat
from pathlib import Path

from enabiz_mcp.downloads import _safe_name, save_download


def test_save_download_writes_and_metadata(tmp_path: Path):
    content = b"%PDF-1.4 sentetik test icerigi"
    meta = save_download(content, "rapor.pdf", tmp_path)
    p = Path(meta["saved_path"])
    assert p.exists() and p.read_bytes() == content
    assert meta["byte_size"] == len(content)
    assert meta["sha256"] == hashlib.sha256(content).hexdigest()
    assert meta["content_type"] == "application/pdf"
    assert stat.S_IMODE(p.stat().st_mode) == 0o600


def test_safe_name_sanitizes():
    assert _safe_name("a/b c?.pdf") == "a_b_c_.pdf"
    assert _safe_name("////") == "download"
    assert _safe_name("") == "download"
