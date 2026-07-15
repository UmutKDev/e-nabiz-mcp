#!/usr/bin/env python
"""Faz 3b HEDEFLİ YAKALAMA — operatör aracı (MCP tool DEĞİL, salt-okunur).

Keşif taramasının atladığı 3 yanıtı canlı yakalar (yapıları sonra parser yazmak için):
  1. COVID tahlilleri  → POST /Tahlil/Index {..., activeTab: "1"} → #tblTahlilCovid19
  2. Tahlil trend      → GET  /Tahlil/TahlillerRapor {IslemTipi} (IslemTipi taze
                          tahlil yanıtındaki GrafikGoster('...') argümanından alınır)
  3. Ziyaret detayı    → GET  /Ziyaret/GetZiyaretDetay?<qs> (qs taze /Ziyaret/Index
                          yanıtındaki kartın onclick'inden alınır)

Tüm çağrılar OKUMA'dır. Token/paramlar taze yanıtlardan çıkarılır (oturuma bağlı
olabilecekleri için). Ham HTML docs/findings/raw/'a (gitignored, chmod 600) yazılır;
terminale yalnız PHI-güvenli YAPI özeti (id/kolon-etiketi/satır-sayısı) basılır.

Kullanım:  uv run python scripts/capture_faz3b.py
Giriş insan-döngüdedir (SMS OTP). `scripts/discover.py`'nin login/save yardımcıları
importlib ile yeniden kullanılır (kod tekrarı yok).
"""

from __future__ import annotations

import datetime
import importlib.util
import re
from pathlib import Path

from bs4 import BeautifulSoup

from enabiz_mcp import auth, discovery
from enabiz_mcp.client import xhr_post
from enabiz_mcp.config import Config

# scripts/discover.py'yi dosyadan yükle (paket değil) → login/save yardımcılarını al.
_SPEC = importlib.util.spec_from_file_location(
    "discover", Path(__file__).resolve().parent / "discover.py"
)
_discover = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_discover)  # type: ignore[union-attr]
ensure_login = _discover.ensure_login
_save_raw = _discover._save_raw
_log = _discover._log

RAW_DIR = Path("docs/findings/raw")

TAHLIL_PAGE = "/Home/Tahlillerim"
TAHLIL_INDEX = "/Tahlil/Index"
TREND_PATH = "/Tahlil/TahlillerRapor"
ZIYARET_PAGE = "/Home/Ziyaretlerim"
ZIYARET_INDEX = "/Ziyaret/Index"
VISIT_DETAIL = "/Ziyaret/GetZiyaretDetay"


# --------------------------------------------------------------------------- #
# PHI-güvenli yapı özeti
# --------------------------------------------------------------------------- #
def _structure(html: str) -> dict:
    """Yalnız YAPI: container seçicileri + tablo id/kolon-etiketleri + satır sayısı.

    Kolon başlıkları (thead th) alan etiketleridir — PHI değil. Hücre değeri YOK.
    """
    soup = BeautifulSoup(html, "html.parser")
    tables = {}
    for t in soup.select("table[id]"):
        ths = [th.get_text(" ", strip=True) for th in t.select("thead th")]
        tables[t["id"]] = {
            "columns": [c for c in ths if c],
            "rows": len(t.select("tbody tr")),
        }
    return {
        "byte_size": len(html.encode("utf-8", "ignore")),
        "containers": discovery.detect_containers(html),
        "tables": tables,
    }


def _first_islem_tipi(html: str) -> str | None:
    m = re.search(r"GrafikGoster\('([^']+)'\)", html)
    return m.group(1) if m else None


def _first_visit_detail_qs(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all(lambda t: t.has_attr("onclick") and "GetZiyaretDetay" in t["onclick"]):
        m = re.search(r"GetZiyaretDetay\?([^'\"]+)", a["onclick"])
        if m:
            return m.group(1)
    return None


# --------------------------------------------------------------------------- #
# Yakalamalar
# --------------------------------------------------------------------------- #
def capture_covid(client, start: int, end: int) -> None:
    token = auth.scrape_token(client, TAHLIL_PAGE)
    resp = xhr_post(
        client,
        TAHLIL_INDEX,
        token,
        {"baslangicTarihi": str(start), "bitisTarihi": str(end), "activeTab": "1"},
        referer=TAHLIL_PAGE,
    )
    _save_raw(RAW_DIR / "tahlil_covid_partial.html", resp.text)
    _log(f"[COVID] {resp.status_code} → yapı: {_structure(resp.text)}")


def capture_trend(client, start: int, end: int) -> None:
    # IslemTipi'yi taze bir tahlil (activeTab=0) yanıtından al.
    token = auth.scrape_token(client, TAHLIL_PAGE)
    labs = xhr_post(
        client,
        TAHLIL_INDEX,
        token,
        {"baslangicTarihi": str(start), "bitisTarihi": str(end), "activeTab": "0"},
        referer=TAHLIL_PAGE,
    )
    islem = _first_islem_tipi(labs.text)
    if not islem:
        _log("[TREND] atlandı: taze tahlilde GrafikGoster/IslemTipi bulunamadı.")
        return
    resp = client.get(TREND_PATH, params={"IslemTipi": islem})
    _save_raw(RAW_DIR / "tahlil_trend_partial.html", resp.text)
    _log(f"[TREND] IslemTipi=<gizli> {resp.status_code} → yapı: {_structure(resp.text)}")


def capture_visit_detail(client, start: int, end: int) -> None:
    token = auth.scrape_token(client, ZIYARET_PAGE)
    lst = xhr_post(
        client,
        ZIYARET_INDEX,
        token,
        {"baslangicYil": str(start), "bitisYil": str(end)},
        referer=ZIYARET_PAGE,
    )
    qs = _first_visit_detail_qs(lst.text)
    if not qs:
        _log("[ZİYARET-DETAY] atlandı: kartlarda GetZiyaretDetay onclick bulunamadı.")
        return
    resp = client.get(f"{VISIT_DETAIL}?{qs}")
    _save_raw(RAW_DIR / "ziyaret_detay_partial.html", resp.text)
    _log(f"[ZİYARET-DETAY] {resp.status_code} → yapı: {_structure(resp.text)}")


def main() -> int:
    cfg = Config.from_env()
    ensure_login(cfg)
    this_year = datetime.date.today().year
    start, end = this_year - 10, this_year  # geniş aralık (veri bulma şansı)

    _log("\nHedefli yakalama başlıyor (COVID · trend · ziyaret-detay)...")
    with auth.session_scope(cfg) as client:
        for name, fn in (
            ("COVID", capture_covid),
            ("TREND", capture_trend),
            ("ZİYARET-DETAY", capture_visit_detail),
        ):
            try:
                fn(client, start, end)
            except auth.AuthRequired:
                _log(f"⚠ Oturum düştü ({name}). Yeniden giriş gerekli — durduruluyor.")
                return 1
            except Exception as exc:  # noqa: BLE001 — biri hata verse de diğerleri denensin
                _log(f"✗ {name} hata: {type(exc).__name__}: {exc}")

    _log(f"\n✓ Ham yakalamalar → {RAW_DIR}/ (gitignored). Yapı özetleri yukarıda (PHI yok).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
