"""`enabiz_download_document` testleri — ağ yok (httpx.MockTransport).

Dört ayrı PDF tool'unun yerine geçer. Boş/HTML yanıt guard'ı eskiden yalnız
radyolojide vardı; epikriz/patoloji bozuk içeriği PDF diye kaydedip sha256'sıyla
"başarılı" diyordu.
"""

from __future__ import annotations

import base64
import contextlib
import json

import httpx
import pytest

from enabiz_mcp import auth
from enabiz_mcp.tools import download

_TOKEN = '<input name="__RequestVerificationToken" value="tok"/>'
_PDF = b"%PDF-1.4\n%fake pdf bytes for test\n%%EOF"


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict = {}

    def tool(self, **_kw):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn

        return deco


@pytest.fixture
def tool(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABIZ_DOWNLOAD_DIR", str(tmp_path))

    def _make(body: bytes, content_type: str = "application/pdf"):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and "Home" in request.url.path:
                return httpx.Response(200, text=_TOKEN)  # scrape_token
            if request.url.path.endswith("GetRaporPdfByOrder"):
                payload = {"rapor": base64.b64encode(body).decode()} if body else {}
                return httpx.Response(200, text=json.dumps(payload))
            return httpx.Response(
                200, content=body, headers={"content-type": content_type}
            )

        client = httpx.Client(
            base_url="https://enabiz.gov.tr", transport=httpx.MockTransport(handler)
        )

        @contextlib.contextmanager
        def fake_scope(_cfg):
            yield client

        monkeypatch.setattr(auth, "session_scope", fake_scope)
        fake = _FakeMCP()
        download.register(fake)
        return fake.tools["enabiz_download_document"]

    return _make


@pytest.mark.parametrize(
    ("kind", "kwargs"),
    [
        ("pathology", {"reference_no": "REF1", "sys_no": "SYS1"}),
        ("discharge", {"reference_no": "REF2", "sys_no": "SYS2"}),
        ("radiology", {"order_id": "ORD1"}),
        ("lab", {"card_tarih": "01.01.2024", "kurum_kodu": "K1"}),
    ],
)
def test_all_four_kinds_save_pdf(tool, kind, kwargs):
    """Dört alan da tek tool'dan, aynı zarfla iner."""
    out = tool(_PDF)(kind=kind, **kwargs)
    assert out["kind"] == kind
    assert out["byte_size"] == len(_PDF)
    assert out["sha256"]
    assert out["saved_path"].endswith(".pdf")
    # İçerik LLM'e verilmez — yalnız metadata.
    assert "content" not in out and "rapor" not in out


def test_saved_file_is_chmod_600(tool, tmp_path):
    out = tool(_PDF)(kind="pathology", reference_no="REF1", sys_no="SYS1")
    from pathlib import Path

    assert Path(out["saved_path"]).stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("kind", ["pathology", "discharge", "radiology", "lab"])
def test_empty_response_is_rejected(tool, kind):
    """Eskiden epikriz/patoloji 0 baytı PDF diye kaydedip 'başarılı' diyordu."""
    kw = {"pathology": {"reference_no": "R", "sys_no": "S"},
          "discharge": {"reference_no": "R", "sys_no": "S"},
          "radiology": {"order_id": "O"},
          "lab": {"card_tarih": "01.01.2024", "kurum_kodu": "K"}}[kind]
    out = tool(b"")(kind=kind, **kw)
    assert out["error"] == "no_pdf"
    assert "saved_path" not in out


def test_html_error_page_is_not_saved_as_pdf(tool):
    """Asıl bonus: HTML hata sayfası %PDF- ile başlamaz → kaydedilmemeli."""
    out = tool(b"<html><body>Bir hata olustu</body></html>", "text/html")(
        kind="discharge", reference_no="R", sys_no="S"
    )
    assert out["error"] == "not_a_pdf"
    assert "saved_path" not in out


def test_unknown_kind(tool):
    out = tool(_PDF)(kind="tarif")
    assert out["error"] == "unknown_kind"
    assert "lab" in out["hint"]


def test_missing_params_are_actionable(tool):
    out = tool(_PDF)(kind="pathology", reference_no="REF1")  # sys_no yok
    assert out["error"] == "missing_params"
    assert "sys_no" in out["message"]
    assert "enabiz_list_pathology" in out["hint"]  # nereden alınacağını söyler
