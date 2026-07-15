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
  uv run python scripts/discover_mhrs.py                  # tam tarama (canlı)
  uv run python scripts/discover_mhrs.py --max-chunk-id 200
  uv run python scripts/discover_mhrs.py --no-save-raw    # yalnız rapor
  uv run python scripts/discover_mhrs.py --from-raw       # AĞSIZ, kayıtlı bundle'dan

`--from-raw` neden var: çıkarıcı/sınıflandırıcı değiştiğinde bundle DEĞİŞMEZ. Raporu
yenilemek için portala 90 istek daha atmak hem gereksiz bir yük, hem de sinsi bir
tutarsızlık kaynağıdır — aradan bir deploy geçtiyse rapor yeni build'e kayar ama
`docs/findings/mhrs.md`'deki elle yazılmış bulgular eski build'i anlatmaya devam
eder. Kayıtlı byte'lardan üretmek aynı build'e sabit kalır. (Bu mod tam olarak şu
yüzden eklendi: `kurum-rss/` prefix'i allowlist'ten düşmüştü ve düzeltmek yalnız
regex'i değiştirmeyi gerektiriyordu.)

Chunk id'leri ve cache-buster (`?t=<ms>`, `?v<sürüm>`) her deploy'da değişir; bu
betik onları ASLA sabit kodlamaz — şablonu her koşuda `main.js`'ten yeniden okur.
Saf mantık `enabiz_mcp.mhrs.discovery`'de (test edilir).
"""

from __future__ import annotations

import argparse
import re
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


def load_raw_sources(raw_dir: Path) -> tuple[list[tuple[str, str]], dict]:
    """Kayıtlı bundle'dan kaynakları okur — **hiç ağ yok**.

    Kaynak adları canlı moddakiyle BİREBİR aynı üretilir (`main`, `chunk-<id>`) ve
    chunk'lar SAYISAL sırayla yüklenir — canlı moddaki `range(max_chunk_id + 1)`
    sırasının aynısı. Sıra kozmetik değil: `collect_calls` tekilleştirmede "ilk
    kaynak kazanır" der, yani yükleme sırası raporun "Kaynak" sütununu belirler.
    Dosya adlarını sözlük sırasıyla okumak (`vatandas-10` < `vatandas-2`) iki uca
    farklı chunk atamıştı — ölçüldü, kaynak sütunu kaydı.

    `build_version` `main.js`'ten okunur: canlı modda `index.html` yorumundan alınır,
    ama aynı damga main bundle'ında da bulunuyor — yani index.html'i saklamaya gerek
    kalmıyor.
    """
    main_path = raw_dir / "vatandas-main.js"
    if not main_path.exists():
        sys.exit(
            f"HATA: {main_path} yok. --from-raw kayıtlı bir taramaya ihtiyaç duyar; "
            "önce --from-raw olmadan canlı tarama koştur."
        )
    main_text = main_path.read_text(encoding="utf-8", errors="replace")
    sources: list[tuple[str, str]] = [("main", main_text)]

    chunk_re = re.compile(r"vatandas-(\d+)-chunk\.js$")
    found: list[tuple[int, Path]] = []
    for p in raw_dir.glob("vatandas-*-chunk.js"):
        m = chunk_re.search(p.name)
        if m:
            found.append((int(m.group(1)), p))

    chunk_ids: list[int] = []
    for cid, p in sorted(found):  # SAYISAL sıra — canlı moddaki range() ile aynı
        chunk_ids.append(cid)
        sources.append((f"chunk-{cid}", p.read_text(encoding="utf-8", errors="replace")))

    version = discovery.extract_build_version(main_text)
    _log(f"kayıtlı bundle: {raw_dir} · build {version or '?'} · "
         f"main + {len(chunk_ids)} chunk · AĞ YOK")

    # `chunks_scanned` BİLİNÇLİ olarak yok: bu modda hiçbir şey taranmadı, okundu.
    # Canlı taramanın kaç id denediğini bilmiyoruz ve uydurmak raporu yalancı yapar.
    meta = {
        "build_version": version or "?",
        "chunks_read": len(chunk_ids),
        "source": "kayıtlı bundle (--from-raw)",
    }
    return sources, meta


#: Yol gibi görünen ama API OLMAYAN prefix'ler (Draft.js CSS classname'leri).
NON_API_PREFIXES = frozenset({"public"})

#: Genel "prefix/..." deseni — çıkarıcının DAR regex'inin aksine allowlist uygulamaz.
#: İkisinin farkı tam olarak allowlist'in kör noktasıdır.
#:
#: `/?` şart: denetçinin kendisi de bir tur baştaki slash'ı reddediyordu, yani
#: çıkarıcıyla AYNI kör noktayı paylaşıyordu — kör noktayı arayan araç aynı kör
#: noktaya sahipse hiçbir şey bulmaz. 7 uç (`parola-degistir` dahil) ikisinden de
#: kaçmıştı.
_GENERIC_CALL_RE = re.compile(
    r"""\.(?:get|post|put|delete)\(\s*["']/?([a-z][a-z0-9-]*)/""", re.IGNORECASE
)


def audit_unknown_prefixes(sources: list[tuple[str, str]]) -> dict[str, int]:
    """Allowlist dışında kalan yol-benzeri prefix'leri sayar ve döndürür.

    Neden var: `API_PREFIXES` bir allowlist'tir; güvenlidir çünkü daraltır, ama
    SESSİZCE daraltır. `kurum-rss/` bir tur listede yoktu ve slot arama uçlarının
    ikisi de rapora hiç girmedi — rapor 151 uçla eksiksiz GÖRÜNÜYORDU. Boşluk ancak
    bundle elle taranınca fark edildi.

    Tarayıcı artık kendi kör noktasına bakıyor: düşen her prefix rapora yazılır ve
    operatöre bildirilir. Sessiz daraltma → gürültülü daraltma.
    """
    counts: dict[str, int] = {}
    known = {p.rstrip("/") for p in discovery.API_PREFIXES} | NON_API_PREFIXES
    for _name, js in sources:
        for m in _GENERIC_CALL_RE.finditer(js):
            seg = m.group(1).lower()
            if seg not in known:
                counts[seg] = counts.get(seg, 0) + 1
    return counts


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
    ap.add_argument("--from-raw", action="store_true",
                    help="Ağa çıkma; raporu --out'taki kayıtlı bundle'dan üret.")
    args = ap.parse_args(argv)

    if args.from_raw:
        sources, meta = load_raw_sources(args.out)
    else:
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

    unknown_prefixes = audit_unknown_prefixes(sources)
    if unknown_prefixes:
        summary = " · ".join(f"{k}/ ×{v}" for k, v in sorted(unknown_prefixes.items()))
        _log(f"\n⚠️  ALLOWLIST DIŞI PREFIX: {summary}")
        _log("   Bu çağrı yerleri ÇIKARILMADI ve rapora GİRMEDİ. API ise "
             "discovery.API_PREFIXES'e, değilse NON_API_PREFIXES'e ekle.")

    calls = collect_calls(sources)
    rows = [
        MhrsReportRow(method=c.method, path=c.path, verdict=c.verdict, source=c.source)
        for c in calls
    ]
    counts = {v: sum(1 for r in rows if r.verdict == v) for v in ("read", "write", "unknown")}
    meta.update(endpoints=len(rows), **counts)
    # Kör nokta rapora da yazılır: okuyan kişi "153 uç" sayısının TAM mı yoksa
    # allowlist'in gösterdiği kadar mı olduğunu bilmeli.
    if unknown_prefixes:
        meta["cikarilmayan_prefix"] = ", ".join(sorted(unknown_prefixes))

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(discovery.build_mhrs_report(rows, meta), encoding="utf-8")

    _log(f"\n✓ PHI-güvenli rapor → {args.summary}")
    if not args.from_raw and not args.no_save_raw:
        _log(f"  ham bundle → {args.out}/ (gitignored)")
    _log(f"  özet: {meta}")
    _log(f"\n  {counts['write']} yazma ucu listelendi — hiçbiri ÇAĞRILMADI "
         f"(bu betik yalnız statik JS okur).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
