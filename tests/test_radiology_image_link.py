"""`enabiz_get_radiology_image_link` tool testleri — ağ yok (httpx.MockTransport).

Bu uç, gövdeyi doğrulamadan döndürdüğü için beklenmeyen bir yanıt (WAF ara sayfası,
işlenmemiş 5xx) tüm HTML dokümanını "link" diye LLM bağlamına enjekte ediyordu.
"""

from __future__ import annotations

import contextlib

import httpx
import pytest

from enabiz_mcp import auth
from enabiz_mcp.tools import radiology

_TOKEN = '<input name="__RequestVerificationToken" value="tok"/>'


class _FakeMCP:
    """`register()`'ın kaydettiği closure'ları yakalar (FastMCP iç yapısına bağlanmadan)."""

    def __init__(self) -> None:
        self.tools: dict = {}

    def tool(self, **_kw):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn

        return deco


@pytest.fixture
def image_link_tool(monkeypatch):
    def _make(body: str, status: int = 200):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, text=_TOKEN)  # scrape_token
            return httpx.Response(status, text=body)

        client = httpx.Client(
            base_url="https://enabiz.gov.tr", transport=httpx.MockTransport(handler)
        )

        @contextlib.contextmanager
        def fake_scope(_cfg):
            yield client

        monkeypatch.setattr(auth, "session_scope", fake_scope)
        fake = _FakeMCP()
        radiology.register(fake)
        return fake.tools["enabiz_get_radiology_image_link"]

    return _make


def test_returns_valid_url(image_link_tool):
    tool = image_link_tool("https://viewer.example/dicom?acc=ACC111")
    out = tool("ACC111")
    assert out["image_link"] == "https://viewer.example/dicom?acc=ACC111"
    assert "error" not in out


def test_empty_body_returns_none_not_error(image_link_tool):
    """Görüntüsü olmayan çalışma boş gövde döndürür — bu bir hata değil."""
    out = image_link_tool("")("ACC999")
    assert out["image_link"] is None
    assert "error" not in out


def test_html_body_is_rejected_not_injected(image_link_tool):
    """Asıl düzeltme: HTML gövdesi 'link' diye bağlama sızmamalı."""
    waf_page = "<html><body>" + ("Erişiminiz engellendi. " * 500) + "</body></html>"
    out = image_link_tool(waf_page)("ACC111")
    assert out["error"] == "unexpected_response"
    assert "image_link" not in out
    assert len(out["body_preview"]) <= 200  # tam doküman değil
    assert "hint" in out


def test_non_url_body_is_rejected(image_link_tool):
    out = image_link_tool("Bir hata oluştu")("ACC111")
    assert out["error"] == "unexpected_response"


def test_overlong_url_is_rejected(image_link_tool):
    out = image_link_tool("https://viewer.example/" + "a" * 3000)("ACC111")
    assert out["error"] == "unexpected_response"
