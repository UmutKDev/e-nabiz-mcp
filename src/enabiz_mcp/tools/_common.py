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
    """Oturum/MHRS hatalarını aksiyon-alınabilir hata sözlüklerine çevirir.

    Böylece her veri tool'u try/except tekrarlamak yerine gövdesinde serbestçe
    `auth.session_scope` / `auth.scrape_token` kullanabilir; oturum düşerse tool
    çökmez, `{"error": ..., ...}` döner. `functools.wraps`, FastMCP'nin
    imza/tip çıkarımını koruması için gereklidir.

    MHRS hataları ayrı sınıflar hâlinde geçer, çünkü modelin alması gereken aksiyon
    farklıdır:

    - `rate_limited` (RNDS1000) — **model TEKRAR DENEMEMELİ.** Retry kilidi
      derinleştirir ve kullanıcıyı online randevudan tamamen çıkarır; kayıp hız
      değil, ERİŞİM'dir. Hata mesajı bunu açıkça söyler, yoksa model "geçici hata"
      sanıp döngüye girer — bu tool'ların yapabileceği en pahalı hata.
    - `auth_required` — MHRS oturumu düşmüş; e-Nabız oturumu ayakta olabilir, o
      yüzden ipucu e-Nabız login'ini DEĞİL zincirin yeniden koşmasını işaret eder.
    - `mhrs_error` — sunucu `success: false` dedi; kodu modele geçir ki ne olduğunu
      söyleyebilsin (ör. RND4105 = seçili slot dolmuş).
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict:
        # Yerel import: `tools/` → `mhrs/` bağımlılığı modül yükleme sırasında
        # döngü kurmasın (mhrs.client `..client`'ı, o da config'i çeker).
        from ..mhrs.auth import MhrsAuthRequired, MhrsError, MhrsRateLimited

        try:
            return fn(*args, **kwargs)
        except auth.AuthRequired as exc:
            return {
                "error": "auth_required",
                "message": str(exc),
                "hint": "enabiz_login_start → enabiz_login_verify ile yeniden giriş yapın.",
            }
        except MhrsRateLimited as exc:
            return {
                "error": "rate_limited",
                "message": str(exc),
                "kodu": exc.kodu,
                "hint": (
                    "TEKRAR DENEMEYİN. Bu bir hız sınırı değil, anti-bot kilididir: "
                    "yeniden sorgulamak kilidi derinleştirir ve kullanıcıyı online "
                    "randevudan çıkarır. Kullanıcıya durumu bildirin; kilit sürerse "
                    "MHRS'nin yönlendirdiği kanal Alo 182'dir."
                ),
            }
        except MhrsAuthRequired as exc:
            return {
                "error": "auth_required",
                "message": str(exc),
                "kodu": exc.kodu,
                "hint": (
                    "MHRS oturumu geçersiz. Bir sonraki MHRS tool çağrısı SSO zincirini "
                    "kendiliğinden yeniden koşturur; e-Nabız oturumu da düşmüşse önce "
                    "enabiz_login_start → enabiz_login_verify gerekir."
                ),
            }
        except MhrsError as exc:
            return {"error": "mhrs_error", "message": str(exc), "kodu": exc.kodu}

    return wrapper
