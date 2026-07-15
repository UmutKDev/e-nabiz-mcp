#!/usr/bin/env python
"""MHRS bundle KEŞİF tarayıcısı — operatör aracı (MCP tool DEĞİL).

`prd.mhrs.gov.tr` vatandaş SPA'sinin public statik JS bundle'ını indirir ve
istemcinin çağırdığı tüm API uçlarını çıkarır.

`scripts/discover.py`'den TEMEL farkı: **kimlik doğrulama YOKTUR.** e-Nabız keşfi
ilk iş `ensure_login` çağırır (SMS OTP, insan-döngüde); MHRS keşfi hiçbir şeye giriş
yapmaz, `/api/`'ye tek bir istek atmaz ve hiç PHI görmez — indirdiği her byte,
tarayıcıyla siteye giren herkese zaten açık olan statik JS'tir. Bu yüzden TTY gate,
OTP ve TCKN tripwire'ı gerekmez.

Çıktılar:
  - Ham bundle → docs/findings/raw/mhrs/*.js (gitignored, chmod 600)
  - PHI-güvenli özet → docs/findings/mhrs-discovery-report.md (commit'lenebilir)

Kullanım:
  uv run python scripts/discover_mhrs.py                  # tam tarama
  uv run python scripts/discover_mhrs.py --max-chunk-id 200
  uv run python scripts/discover_mhrs.py --no-save-raw    # yalnız rapor

Chunk id'leri ve cache-buster (`?t=<ms>`, `?v<sürüm>`) her deploy'da değişir; bu
betik onları ASLA sabit kodlamaz — şablonu her koşuda `main.js`'ten yeniden okur.
Saf mantık `enabiz_mcp.mhrs.discovery`'de (test edilir).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

from enabiz_mcp.config import Config
from enabiz_mcp.mhrs import discovery
from enabiz_mcp.mhrs.client import bundle_client
from enabiz_mcp.mhrs.discovery import MhrsCall, MhrsReportRow

DEFAULT_RAW_DIR = Path("docs/findings/raw/mhrs")
DEFAULT_SUMMARY = Path("docs/findings/mhrs-discovery-report.md")


def _log(msg: str) -> None:
    """Operatör bilgisi (PHI/secret İÇERMEZ — zaten hiç görmüyoruz)."""
    print(msg, flush=True)


def _save_raw(path: Path, text: str) -> None:
    """Ham bundle'ı sıkı izinli yazar. PHI değil, ama gereksiz yere paylaşılmaz."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)


def fetch_bundle_sources(
    client: httpx.Client,
    *,
    max_chunk_id: int,
    out_dir: Path,
    save_raw: bool,
) -> tuple[list[tuple[str, str]], dict]:
    """index.html → main.js → lazy chunk'lar. (ad, kaynak) listesi ve meta döndürür."""
    index = client.get(discovery.BUNDLE_INDEX)
    index.raise_for_status()
    version = discovery.extract_build_version(index.text)
    srcs = discovery.extract_script_srcs(index.text)
    _log(f"index.html: {index.status_code} · build {version or '?'} · {len(srcs)} yerel script")

    main_src = next((s for s in srcs if "main" in s), None)
    if main_src is None:
        sys.exit(f"HATA: index.html'de main bundle bulunamadı (script'ler: {srcs})")

    main_url = discovery.BUNDLE_INDEX + main_src.lstrip("./")
    main = client.get(main_url)
    main.raise_for_status()
    _log(f"main bundle: {len(main.text):,} byte")

    sources: list[tuple[str, str]] = [("main", main.text)]
    if save_raw:
        _save_raw(out_dir / "vatandas-main.js", main.text)

    tpl = discovery.extract_chunk_template(main.text)
    if tpl is None:
        # Sessizce devam ETME: chunk'lar olmadan randevu API'si TAMAMEN kaçar
        # (main'de "slot" sıfır kez geçer). Eksik harita, boş haritadan kötüdür.
        sys.exit(
            "HATA: lazy-chunk şablonu main.js'te bulunamadı — webpack çıktısı değişmiş "
            "olabilir. Chunk'lar olmadan randevu uçları görünmez; rapor yazılmadı."
        )
    _log(f"chunk şablonu: {tpl.public_path}{tpl.prefix}<id>{tpl.suffix}")
    _log(f"  main'de .e() ile referans verilen: {len(tpl.referenced_ids)} id — "
         f"ama TAM küme bu değil, 0..{max_chunk_id} taranıyor")

    found, missing = [], []
    for cid in range(max_chunk_id + 1):
        r = client.get(tpl.url_for(cid))
        # Yoksa portal 302 (login'e) döner, 404 değil.
        if r.status_code != 200 or "javascript" not in r.headers.get("content-type", ""):
            missing.append(cid)
            continue
        found.append(cid)
        sources.append((f"chunk-{cid}", r.text))
        if save_raw:
            _save_raw(out_dir / f"vatandas-{cid}-chunk.js", r.text)

    _log(f"chunk: {len(found)} bulundu, {len(missing)} yok"
         + (f" (yok: {missing[:12]}{'…' if len(missing) > 12 else ''})" if missing else ""))

    meta = {
        "build_version": version or "?",
        "chunks_found": len(found),
        "chunks_scanned": max_chunk_id + 1,
    }
    return sources, meta


def collect_calls(sources: list[tuple[str, str]]) -> list[MhrsCall]:
    """Tüm kaynaklardan çağrıları çıkarır ve (method, path)'e göre tekilleştirir."""
    uniq: dict[tuple[str, str], MhrsCall] = {}
    for name, js in sources:
        for call in discovery.extract_calls(js, source=name):
            uniq.setdefault((call.method, call.path), call)
    return list(uniq.values())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MHRS bundle keşif tarayıcısı (kimliksiz).")
    ap.add_argument("--max-chunk-id", type=int, default=128,
                    help="Taranacak en yüksek lazy-chunk id'si (varsayılan 128).")
    ap.add_argument("--out", type=Path, default=DEFAULT_RAW_DIR, help="Ham bundle dizini.")
    ap.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY, help="Rapor yolu.")
    ap.add_argument("--no-save-raw", action="store_true", help="Ham bundle'ı diske yazma.")
    args = ap.parse_args(argv)

    cfg = Config.from_env()
    _log(f"MHRS bundle taraması · {discovery.BUNDLE_ORIGIN}{discovery.BUNDLE_INDEX} · "
         f"kimlik doğrulama YOK · /api/'ye istek YOK")

    with bundle_client(cfg) as client:
        sources, meta = fetch_bundle_sources(
            client,
            max_chunk_id=args.max_chunk_id,
            out_dir=args.out,
            save_raw=not args.no_save_raw,
        )

    calls = collect_calls(sources)
    rows = [
        MhrsReportRow(method=c.method, path=c.path, verdict=c.verdict, source=c.source)
        for c in calls
    ]
    counts = {v: sum(1 for r in rows if r.verdict == v) for v in ("read", "write", "unknown")}
    meta.update(endpoints=len(rows), **counts)

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(discovery.build_mhrs_report(rows, meta), encoding="utf-8")

    _log(f"\n✓ PHI-güvenli rapor → {args.summary}")
    if not args.no_save_raw:
        _log(f"  ham bundle → {args.out}/ (gitignored)")
    _log(f"  özet: {meta}")
    _log(f"\n  {counts['write']} yazma ucu listelendi — hiçbiri ÇAĞRILMADI "
         f"(bu betik yalnız statik JS okur).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
