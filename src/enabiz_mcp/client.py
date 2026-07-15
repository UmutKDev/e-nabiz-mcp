"""Kimlikli HTTP istemcisi.

`httpx.Client` cookie jar'ı istekler arası otomatik taşır. XSRF korumalı POST'lar
için `xhr_post` yardımcı fonksiyonu antiforgery token'ını `XSRF-TOKEN` header'ı
olarak ekler (portalın jQuery `ajaxSetup` davranışını taklit eder).
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Mapping
from typing import Any

import httpx

from .config import Config


class _Throttle:
    """İstekler arası minimum aralığı zorlayan basit hız sınırlayıcı.

    Portalın WAF'ını (SAGLIK* cookie) tetiklememek için her istekten önce, son
    istekten bu yana `min_interval` saniye geçmemişse aradaki farkı bekler.

    Durum (`_last`) client'ı DEĞİL süreci kapsar: her tool çağrısı yeni bir client
    kurar (`auth.session_scope` → `build_client`), dolayısıyla throttle client'a
    bağlı olsaydı her tool'un ilk isteği sınırsız geçerdi — korunmak istenen şey
    tam da ardışık tool çağrıları. Bkz. `_throttle_for`.
    """

    def __init__(self, min_interval: float) -> None:
        self.min_interval = max(0.0, min_interval)
        # -inf: ilk istek beklemez, ama "0.0 vs monotonic()" tesadüfüne değil
        # açık bir karara dayanarak.
        self._last = -math.inf
        self._lock = threading.Lock()

    def __call__(self, request: httpx.Request) -> None:  # httpx request event hook
        if self.min_interval <= 0:
            return
        # FastMCP sync tool'ları worker thread'lerde koşturur; _last'ın
        # read-modify-write'ı kilitsiz olursa iki tool aynı anda geçebilir.
        with self._lock:
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()


_throttles: dict[float, _Throttle] = {}
_throttles_lock = threading.Lock()


def _throttle_for(min_interval: float) -> _Throttle:
    """`min_interval` için süreç-genelinde paylaşılan throttle'ı döndürür."""
    with _throttles_lock:
        throttle = _throttles.get(min_interval)
        if throttle is None:
            throttle = _Throttle(min_interval)
            _throttles[min_interval] = throttle
        return throttle


def build_client(cfg: Config, cookies: httpx.Cookies | None = None) -> httpx.Client:
    """Portal için yapılandırılmış senkron `httpx.Client` üretir (hız sınırlı)."""
    headers = {
        "User-Agent": cfg.user_agent,
        "Accept-Language": "tr,en;q=0.9",
        "Accept": "*/*",
    }
    return httpx.Client(
        base_url=cfg.base_url,
        headers=headers,
        follow_redirects=True,
        timeout=30.0,
        cookies=cookies,
        event_hooks={"request": [_throttle_for(cfg.min_interval)]},
    )


def xhr_post(
    client: httpx.Client,
    path: str,
    token: str,
    data: Mapping[str, Any],
    *,
    referer: str = "/Account/Login",
) -> httpx.Response:
    """XSRF korumalı bir AJAX POST gönderir.

    `token`: `GET /Account/Login`'den kazınan `__RequestVerificationToken` değeri.
    """
    headers = {
        "XSRF-TOKEN": token,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": str(client.base_url).rstrip("/"),
        "Referer": f"{str(client.base_url).rstrip('/')}{referer}",
    }
    return client.post(path, data=dict(data), headers=headers)
