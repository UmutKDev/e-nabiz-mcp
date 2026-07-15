"""`scripts/discover.py` scan_page entegrasyon testi — ağ yok (httpx.MockTransport).

Tüm replay hattını doğrular: sayfa GET → uç çıkarımı → token kazıma → xhr_post →
ham yakalama + rapor satırı. En kritik: **yazma ucu ASLA çağrılmaz** (mock handler
çağrılırsa test patlar).
"""

from __future__ import annotations

import importlib.util
import stat
from pathlib import Path

import httpx
import pytest

# scripts/ bir paket değil — dosyadan yükle.
_SPEC = importlib.util.spec_from_file_location(
    "discover", Path(__file__).resolve().parent.parent / "scripts" / "discover.py"
)
discover = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(discover)  # type: ignore[union-attr]

_PAGE = """
<html><body>
<input name="__RequestVerificationToken" value="tok123"/>
<script>
  $.ajax({ url:'/Fake/Index', data:{ startYear:a, endYear:b }, method:'POST',
           success:(d)=>{ $('#tblFake').html(d); } });
  $.ajax({ url:'/Fake/Sil', data:{ id:x }, method:'POST' });   // YAZMA — çağrılmamalı
</script>
</body></html>
"""

_PARTIAL = '<table id="tblFake"><tbody><tr><td>1</td></tr><tr><td>2</td></tr></tbody></table>'


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if request.method == "GET" and path == "/Home/Fake":
        return httpx.Response(200, text=_PAGE)
    if request.method == "POST" and path == "/Fake/Index":
        return httpx.Response(200, text=_PARTIAL)
    if path == "/Fake/Sil":
        raise AssertionError("Yazma ucu (/Fake/Sil) çağrıldı — salt-okunur ihlali!")
    return httpx.Response(404)


def _client() -> httpx.Client:
    return httpx.Client(
        base_url="https://enabiz.gov.tr",
        transport=httpx.MockTransport(_handler),
    )


def test_scan_replays_read_skips_write(tmp_path: Path):
    with _client() as client:
        rows = discover.scan_page(
            client, "fake", "/Home/Fake",
            start_year=2020, end_year=2025, out_dir=tmp_path, dry_run=False,
        )
    by_ep = {r.endpoint: r for r in rows}

    # Okuma ucu replay edildi, satır sayısı partial'dan geldi.
    read = by_ep["/Fake/Index"]
    assert read.verdict == "read"
    assert read.status == 200
    assert read.row_count == 2
    assert read.param_names == ["startYear", "endYear"]

    # Yazma ucu kaydedildi ama replay EDİLMEDİ (handler assertion'ı da patlamadı).
    assert by_ep["/Fake/Sil"].verdict == "not-read(write)"
    assert by_ep["/Fake/Sil"].status is None


def test_scan_writes_chmod600_captures(tmp_path: Path):
    with _client() as client:
        discover.scan_page(
            client, "fake", "/Home/Fake",
            start_year=2020, end_year=2025, out_dir=tmp_path, dry_run=False,
        )
    page_file = tmp_path / "fake.html"
    partial_file = tmp_path / "fake_index_partial.html"
    assert page_file.exists() and partial_file.exists()
    for f in (page_file, partial_file):
        assert stat.S_IMODE(f.stat().st_mode) == 0o600, f


def test_dry_run_does_not_replay(tmp_path: Path):
    with _client() as client:
        rows = discover.scan_page(
            client, "fake", "/Home/Fake",
            start_year=2020, end_year=2025, out_dir=tmp_path, dry_run=True,
        )
    read = {r.endpoint: r for r in rows}["/Fake/Index"]
    assert read.verdict == "read(dry-run)"
    assert read.status is None
    # Dry-run'da partial YAZILMAZ (yalnız menü sayfası kaydedilir).
    assert not (tmp_path / "fake_index_partial.html").exists()
    assert (tmp_path / "fake.html").exists()


def test_scan_raises_on_dropped_session(tmp_path: Path):
    def login_handler(request: httpx.Request) -> httpx.Response:
        # Kimlikli sayfa yerine login formu döner → oturum düşmüş.
        return httpx.Response(200, text='<input name="TCKimlikNo"/>')

    with httpx.Client(
        base_url="https://enabiz.gov.tr", transport=httpx.MockTransport(login_handler)
    ) as client, pytest.raises(discover.auth.AuthRequired):
            discover.scan_page(
                client, "fake", "/Home/Fake",
                start_year=2020, end_year=2025, out_dir=tmp_path, dry_run=False,
            )
