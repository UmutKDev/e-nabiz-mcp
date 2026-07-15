#!/usr/bin/env python
"""E-Nabız salt-okunur KEŞİF tarayıcısı — operatör aracı (MCP tool DEĞİL).

Kimlikli oturumla keşfedilmemiş `/Home/*` menü sayfalarını gezer; her sayfanın
KENDİ `$.ajax` veri-yükleme ucunu çıkarır ve YALNIZ **okuma** olarak sınıflanan,
tüm parametre değerleri bilinen uçları BİR KEZ tekrar oynatır (replay). Yazma/aksiyon
uçlarına asla dokunmaz; sayfadaki `<a href>` linklerini takip etmez.

Çıktılar:
  - Ham HTML  → docs/findings/raw/<slug>.html, <slug>_<action>_partial.html (gitignored, chmod 600)
  - PHI-güvenli özet → docs/findings/discovery-report.md (commit'lenebilir; yalnız yapısal alanlar)

Kullanım:
  uv run python scripts/discover.py --dry-run              # yalnız uç çıkar, REPLAY YOK
  uv run python scripts/discover.py                        # tam tarama (SMS OTP sorulur)
  uv run python scripts/discover.py --pages alerji,asi     # alt küme
  ENABIZ_MIN_INTERVAL=1.5 uv run python scripts/discover.py # WAF'a nazik tarama

Giriş insan-döngüdedir: OTP terminalden `getpass` ile alınır. Şifre `.env`'den okunur;
bu script şifreyi/OTP'yi/ham yanıt gövdesini (PHI) ASLA yazdırmaz. reCAPTCHA/SMS
ATLATILMAZ. Saf mantık `enabiz_mcp.discovery`'de (test edilir).
"""

from __future__ import annotations

import argparse
import datetime
import getpass
import sys
from pathlib import Path

from enabiz_mcp import auth, discovery
from enabiz_mcp.client import xhr_post
from enabiz_mcp.config import Config
from enabiz_mcp.discovery import ReportRow

DEFAULT_RAW_DIR = Path("docs/findings/raw")
DEFAULT_SUMMARY = Path("docs/findings/discovery-report.md")


# --------------------------------------------------------------------------- #
# Yardımcılar
# --------------------------------------------------------------------------- #
def _log(msg: str) -> None:
    """Operatör bilgisi (PHI/secret İÇERMEZ)."""
    print(msg, flush=True)


def _save_raw(path: Path, text: str) -> None:
    """Ham HTML'i sıkı izinli (chmod 600) yazar — PHI olarak muamele edilir."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)


def _action(url: str) -> str:
    seg = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    return "".join(c if c.isalnum() else "_" for c in seg).lower() or "root"


def _meta(resp) -> tuple[int, str, int]:
    return resp.status_code, resp.headers.get("content-type", ""), len(resp.content)


# --------------------------------------------------------------------------- #
# Giriş (insan-döngüde)
# --------------------------------------------------------------------------- #
def _session_alive(cfg: Config) -> bool:
    """Oturum canlı mı — `auth.session_alive`'a delege eder (tek tanım).

    Bu mantık eskiden yalnız burada vardı; `enabiz_session_status` ise cookie'nin
    yalnız ADINA bakıp ölü oturum için "girişlisiniz" diyordu. Artık ikisi de aynı
    fonksiyonu kullanıyor.
    """
    return auth.session_alive(cfg)


def ensure_login(cfg: Config) -> None:
    """Kayıtlı oturum yoksa/geçersizse iki-aşamalı (kimlik + SMS OTP) giriş yapar.

    Şifre `.env`'den okunur (script görmez). OTP `getpass` ile alınır (echo'suz).
    """
    if _session_alive(cfg):
        _log("✓ Kayıtlı kimlikli oturum geçerli — giriş atlanıyor.")
        return

    if not cfg.credentials_configured:
        sys.exit("HATA: ENABIZ_TCKIMLIK / ENABIZ_SIFRE .env'de ayarlı değil.")

    # Güvenlik: giriş SMS OTP gerektirir. Etkileşimli terminal yoksa OTP alınamaz —
    # login_start SMS TETİKLER, o yüzden SMS göndermeden ÖNCE burada dururuz
    # (kazara/otomatik çalıştırmalarda gereksiz SMS'i önler).
    if not sys.stdin.isatty():
        sys.exit(
            "HATA: giriş etkileşimli terminal gerektirir (SMS OTP). "
            "Bu betiği kendi terminalinizde çalıştırın."
        )

    _log("Giriş başlatılıyor (kimlik doğrulama + SMS OTP)...")
    info = auth.login_start(cfg)  # şifreyi env'den kendi okur
    if info.get("step") != "sms_required":
        sys.exit(f"HATA: giriş başlatılamadı — {info.get('message', '')}")

    for _ in range(3):
        otp = getpass.getpass("Telefonunuza gelen SMS onay kodu: ").strip()
        res = auth.login_verify(cfg, otp)
        step = res.get("step")
        if step == "logged_in":
            _log("✓ Giriş başarılı, oturum kaydedildi (chmod 600).")
            return
        if step == "wrong_code":
            _log("✗ Kod eşleşmedi, tekrar deneyin.")
            continue
        sys.exit(f"HATA: giriş başarısız — {res.get('message', '')}")
    sys.exit("HATA: SMS kodu 3 kez yanlış. Çıkılıyor.")


# --------------------------------------------------------------------------- #
# Tarama
# --------------------------------------------------------------------------- #
def scan_page(
    client,
    slug: str,
    page: str,
    *,
    start_year: int,
    end_year: int,
    out_dir: Path,
    dry_run: bool,
) -> list[ReportRow]:
    """Bir menü sayfasını GET eder, uçları çıkarır ve okuma uçlarını replay eder.

    Oturum düşerse `AuthRequired` fırlatır (çağıran temiz durur).
    """
    rows: list[ReportRow] = []
    r = client.get(page)
    html = r.text
    if 'name="TCKimlikNo"' in html:  # login'e yönlendirildi → oturum düşmüş
        raise auth.AuthRequired(f"{page}: oturum düşmüş görünüyor.")

    _save_raw(out_dir / f"{slug}.html", html)
    eps = discovery.extract_ajax_endpoints(html)
    conts = discovery.detect_containers(html)

    status, ctype, size = _meta(r)
    first_cont = conts[0] if conts else None
    rows.append(
        ReportRow(
            page=page, endpoint=page, method="GET", param_names=[], status=status,
            byte_size=size, content_type=ctype, container=first_cont,
            row_count=discovery.count_rows(html, first_cont) if first_cont else None,
            verdict="page(server-render)" if conts else "page",
        )
    )
    _log(f"  {slug:14} sayfa: {status} {size}B · ajax={len(eps)} · container={conts[:3] or '—'}")

    for ep in eps:
        plan = discovery.plan_replay(ep, start_year, end_year)
        if not plan.ok:
            rows.append(_row(page, ep, None, None, "", None, plan.reason))
            continue
        if dry_run:
            rows.append(_row(page, ep, None, None, "", None, "read(dry-run)"))
            continue
        try:
            if plan.method == "GET":
                rr = client.get(ep.url, params=plan.data or None)
            else:
                token = auth.scrape_token(client, page)
                body = dict(plan.data)
                if plan.needs_token_body:
                    body[discovery.TOKEN_PARAM] = token
                rr = xhr_post(client, ep.url, token, body, referer=page)
            st, ct, sz = _meta(rr)
            rc = discovery.count_rows(rr.text, ep.container) if ep.container else None
            _save_raw(out_dir / f"{slug}_{_action(ep.url)}_partial.html", rr.text)
            rows.append(_row(page, ep, st, sz, ct, rc, "read"))
            _log(f"      replay {ep.method} {ep.url} → {st} {sz}B rows={rc}")
        except auth.AuthRequired:
            raise
        except Exception as exc:  # ağ/parse hatası — tara devam et
            rows.append(_row(page, ep, None, None, "", None, f"error:{type(exc).__name__}"))
    return rows


def _row(page, ep, status, size, ctype, rc, verdict) -> ReportRow:
    return ReportRow(
        page=page, endpoint=ep.url, method=ep.method, param_names=ep.param_names,
        status=status, byte_size=size, content_type=ctype, container=ep.container,
        row_count=rc, verdict=verdict,
    )


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="E-Nabız salt-okunur keşif tarayıcısı.")
    ap.add_argument("--pages", help="Virgülle ayrılmış slug alt kümesi (bkz. discovery.PAGES).")
    ap.add_argument("--start-year", type=int, help="Yıl-filtreli uçlar için başlangıç.")
    ap.add_argument("--end-year", type=int, help="Yıl-filtreli uçlar için bitiş.")
    ap.add_argument("--out", type=Path, default=DEFAULT_RAW_DIR, help="Ham HTML dizini.")
    ap.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY, help="PHI-güvenli rapor yolu.")
    ap.add_argument("--dry-run", action="store_true", help="Uçları çıkar; REPLAY yapma.")
    args = ap.parse_args(argv)

    cfg = Config.from_env()

    # Yıl aralığı: varsayılan son 6 takvim yılı (bu yıl - 5 … bu yıl, uçlar dahil).
    this_year = datetime.date.today().year
    start_year = args.start_year or (this_year - 5)
    end_year = args.end_year or this_year

    pages = discovery.PAGES
    if args.pages:
        wanted = {s.strip() for s in args.pages.split(",")}
        pages = [(s, p) for (s, p) in discovery.PAGES if s in wanted]
        if not pages:
            valid = [s for s, _ in discovery.PAGES]
            sys.exit(f"HATA: --pages ile eşleşen slug yok. Geçerli: {valid}")

    ensure_login(cfg)

    _log(f"\nTarama başlıyor · {len(pages)} sayfa · yıl [{start_year}..{end_year}] · "
         f"{'DRY-RUN (replay yok)' if args.dry_run else 'replay: okuma uçları'}")

    all_rows: list[ReportRow] = []
    dropped_at: str | None = None
    with auth.session_scope(cfg) as client:
        for slug, page in pages:
            try:
                all_rows += scan_page(
                    client, slug, page, start_year=start_year, end_year=end_year,
                    out_dir=args.out, dry_run=args.dry_run,
                )
            except auth.AuthRequired:
                dropped_at = slug
                _log(f"⚠ Oturum düştü ({slug}). Kalan sayfalar atlanıyor — yeniden giriş gerekli.")
                break

    replayed = sum(1 for r in all_rows if r.verdict == "read")
    skipped = sum(1 for r in all_rows if r.verdict.startswith(("not-read", "needs-id", "honeypot")))
    meta = {
        "pages_scanned": len({r.page for r in all_rows}),
        "endpoints_found": sum(1 for r in all_rows if r.endpoint != r.page),
        "replayed_read": replayed,
        "skipped": skipped,
        "year_range": f"{start_year}-{end_year}",
        "mode": "dry-run" if args.dry_run else "replay",
    }
    if dropped_at:
        meta["auth_dropped_at"] = dropped_at

    report = discovery.build_report(all_rows, meta=meta)

    # PHI koruma: özette TCKN geçmediğini doğrula (yapısal-alan-only zaten garanti).
    if cfg.tc_kimlik_no and cfg.tc_kimlik_no in report:
        sys.exit("HATA: rapor TCKN içeriyor — yazılmadı (PHI koruması).")

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(report, encoding="utf-8")
    _log(f"\n✓ PHI-güvenli rapor → {args.summary}")
    _log(f"  ham HTML → {args.out}/ (gitignored)")
    _log(f"  özet: {meta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
