"""Veri tool'ları için paylaşılan yardımcılar."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from .. import auth

#: Liste tool'larının varsayılan üst sınırı. Tek başına `enabiz_list_lab_tests`
#: 5 yıllık varsayılan aralıkta model bağlamını dolduracak kadar sonuç/token
#: döndürebiliyor; model bunu her tahlil sorusunda ilk çağıran tool olarak yiyor.
DEFAULT_LIMIT = 50


def apply_limit(items: list, limit: int | None) -> tuple[list, dict]:
    """Listeyi kırpar; zarf alanlarını (`count`/`total`/`truncated`) üretir.

    `limit=0` "sınırsız" demektir (kullanıcı açıkça hepsini istedi). Kırpıldığında
    `truncated: True` döner ki model kesildiğini görüp `*_query` ile daraltsın —
    aksi hâlde kısmi listeyi tam sanır.
    """
    total = len(items)
    effective = DEFAULT_LIMIT if limit is None else limit
    if effective and total > effective:
        items = items[:effective]
    return items, {
        "count": len(items),
        "total": total,
        "truncated": len(items) < total,
    }


def auth_guarded(fn: Callable[..., dict]) -> Callable[..., dict]:
    """`AuthRequired`'ı aksiyon-alınabilir bir hata sözlüğüne çevirir.

    Böylece her veri tool'u try/except tekrarlamak yerine gövdesinde serbestçe
    `auth.session_scope` / `auth.scrape_token` kullanabilir; oturum düşerse tool
    çökmez, `{"error": "auth_required", ...}` döner. `functools.wraps`, FastMCP'nin
    imza/tip çıkarımını koruması için gereklidir.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict:
        try:
            return fn(*args, **kwargs)
        except auth.AuthRequired as exc:
            return {
                "error": "auth_required",
                "message": str(exc),
                "hint": "enabiz_login_start → enabiz_login_verify ile yeniden giriş yapın.",
            }

    return wrapper
