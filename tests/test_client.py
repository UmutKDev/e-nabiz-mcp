"""HTTP istemcisi: XSRF header enjeksiyonu ve hız sınırı testleri (ağ yok)."""

import time
from pathlib import Path

import httpx

from enabiz_mcp.client import _Throttle, _throttle_for, build_client, xhr_post
from enabiz_mcp.config import Config


def test_xhr_post_injects_xsrf_and_headers():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["xsrf"] = request.headers.get("XSRF-TOKEN")
        captured["xrw"] = request.headers.get("X-Requested-With")
        captured["ctype"] = request.headers.get("Content-Type")
        captured["body"] = request.content.decode()
        return httpx.Response(200, text="ok")

    client = httpx.Client(
        base_url="https://enabiz.gov.tr",
        transport=httpx.MockTransport(handler),
    )
    r = xhr_post(client, "/Tahlil/Index", "TOK123", {"activeTab": "0"}, referer="/Home/Tahlillerim")

    assert r.status_code == 200
    assert captured["xsrf"] == "TOK123"
    assert captured["xrw"] == "XMLHttpRequest"
    assert "urlencoded" in captured["ctype"]
    assert "activeTab=0" in captured["body"]


def test_throttle_enforces_min_interval():
    throttle = _Throttle(0.1)
    dummy = httpx.Request("GET", "https://enabiz.gov.tr/")
    start = time.monotonic()
    throttle(dummy)
    throttle(dummy)
    throttle(dummy)  # 3 çağrı → en az 2 aralık beklenmeli
    assert time.monotonic() - start >= 0.2


def test_throttle_disabled_when_zero():
    throttle = _Throttle(0.0)
    dummy = httpx.Request("GET", "https://enabiz.gov.tr/")
    start = time.monotonic()
    for _ in range(5):
        throttle(dummy)
    assert time.monotonic() - start < 0.05


def test_throttle_first_request_is_free():
    """`_last = -inf` → ilk istek beklemez (0.0 tesadüfüne değil, karara dayalı)."""
    throttle = _Throttle(5.0)
    start = time.monotonic()
    throttle(httpx.Request("GET", "https://enabiz.gov.tr/"))
    assert time.monotonic() - start < 0.05


def _cfg(min_interval: float) -> Config:
    return Config(
        tc_kimlik_no=None,
        sifre=None,
        session_path=Path("/tmp/enabiz-test-session.json"),
        min_interval=min_interval,
    )


def test_throttle_is_shared_across_clients():
    """Hız sınırı tool çağrısı sınırını AŞMALI.

    Her tool çağrısı `session_scope` → `build_client` ile YENİ client kurar. Throttle
    client'a bağlı olsaydı (eski davranış) her tool'un ilk isteği sınırsız geçerdi —
    yani ardışık tool çağrıları hiç throttle yemezdi, ki korunmak istenen tam da bu.
    Ölçüldü: eski hâlde 3 ardışık client 0.02s, paylaşılan throttle ile 0.63s.
    """
    cfg = _cfg(0.3)
    hook_a = build_client(cfg).event_hooks["request"][0]
    hook_b = build_client(cfg).event_hooks["request"][0]
    assert hook_a is hook_b
    assert hook_a is _throttle_for(0.3)


def test_throttle_not_shared_across_different_intervals():
    assert _throttle_for(0.3) is not _throttle_for(0.7)
