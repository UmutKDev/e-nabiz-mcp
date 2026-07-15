"""Widget kaynakları: doğru mime, kendine yeterlilik, kayıt bütünlüğü.

Widget iframe'i katı bir CSP altında çalışır. Dışarıdan bir şey yüklemeye
çalışan widget SESSİZCE boş/yarım render eder — tarayıcı konsolu dışında hiçbir
yerde iz bırakmaz. Bu yüzden kendine yeterlilik burada, statik olarak taranır.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from enabiz_mcp.ui import registry, schema
from enabiz_mcp.ui.bundle import BUNDLE_PLACEHOLDER

WIDGETS = Path(__file__).resolve().parent.parent / "src" / "enabiz_mcp" / "ui" / "widgets"

#: Widget KAYNAKLARI taranır, gömülü paket DEĞİL: paket üçüncü taraf, minified
#: ve içinde şema URL'leri geçer. Bizim yazdığımız HTML'in temiz olması gerekir.
SOURCES = sorted(WIDGETS.glob("*.html"))


def _src(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _kod(p: Path) -> str:
    """Yorumları soyulmuş kaynak — yasak deseni ANLATAN yorum, ihlal SAYILMAZ.

    Bu yardımcı olmadan "innerHTML kullanma" diyen bir yorum kendi kuralını
    çiğnemiş görünür ve tripwire yalancı çıkar. Yalancı tripwire, olmayandan
    beterdir: susturulur.
    """
    src = _src(p)
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)  # /* ... */
    src = re.sub(r"(?<!:)//[^\n]*", " ", src)  # // ...  (`https://` korunur)
    return src


def test_widget_dosyalari_var():
    assert SOURCES, "widgets/ boş — kaynak kaydı sessizce boş HTML servis eder"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_dis_kaynak_yuklemez(path):
    """CDN/font/görsel — hiçbiri. CSP engeller, widget boş render eder."""
    src = _src(path)
    for kalip in (
        r'src\s*=\s*["\']https?://',
        r'href\s*=\s*["\']https?://',
        r"@import\s",
        r"<link\b",
        r'from\s+["\']https?://',
        r'import\s*\(\s*["\']https?://',
    ):
        assert not re.search(kalip, src, re.I), f"{path.name}: dış kaynak yükler ({kalip})"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_inline_handler_ve_eval_yok(path):
    """CSP inline handler ve eval'i engeller; ayrıca ikisi de enjeksiyon yüzeyi."""
    src = _kod(path)
    assert not re.search(r"\son\w+\s*=\s*[\"']", src), f"{path.name}: inline event handler"
    assert not re.search(r"\beval\s*\(", src), f"{path.name}: eval()"
    assert not re.search(r"\bnew\s+Function\s*\(", src), f"{path.name}: new Function()"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_phi_innerhtml_ile_basilmaz(path):
    """Veri devlet portalından geliyor — `textContent` dışına çıkma.

    Çıplak kelime değil, KULLANIM aranır (`.innerHTML`) ve yorumlar soyulur:
    aksi hâlde "innerHTML kullanma" diyen bir yorum kendi kuralını ihlal etmiş
    sayılırdı.
    """
    src = _kod(path)
    for kalip in (
        r"\.(innerHTML|outerHTML)\b",
        r"\.insertAdjacentHTML\s*\(",
        r"document\.write\s*\(",
    ):
        assert not re.search(kalip, src), f"{path.name}: {kalip} — enjeksiyon yüzeyi"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_paket_belirteci_var(path):
    assert BUNDLE_PLACEHOLDER in _src(path), f"{path.name}: ext-apps paketi gömülemez"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_fetch_ile_disari_konusmaz(path):
    """Sunucuya erişim TEK yoldan: app.callServerTool(). `fetch` CSP'ye takılır."""
    src = _kod(path)
    assert not re.search(r"\bfetch\s*\(", src), f"{path.name}: fetch() — callServerTool kullan"
    assert not re.search(r"\bXMLHttpRequest\b", src), f"{path.name}: XHR"
    assert not re.search(r"\bWebSocket\s*\(", src), f"{path.name}: WebSocket"


def test_kayitli_kaynak_mime_ve_csp():
    """`text/html;profile=mcp-app`, host'un iframe render etmesini sağlayan TEK sinyal."""
    from enabiz_mcp.server import mcp

    res = {str(r.uri): r for r in asyncio.run(mcp._list_resources())}
    for uri in registry.widget_uris():
        assert uri in res, f"{uri} kaydedilmemiş — tool onu işaret ediyor ama kaynak yok"
        r = res[uri]
        assert r.mime_type == "text/html;profile=mcp-app", f"{uri}: mime {r.mime_type}"
        csp = (r.meta or {}).get("ui", {}).get("csp", {})
        # Boş liste = "hiçbir origin'e izin yok". privacy.md §1-2: iframe dışarı konuşmaz.
        assert csp.get("connectDomains") == [], f"{uri}: connectDomains açık"


def test_her_domain_widgeti_kayitli_bir_kaynaga_cozulur():
    """Sessiz kırık widget yok: `resource_uri` daima gerçek bir kaynağa işaret eder."""
    from enabiz_mcp.server import mcp

    kayitli = {str(r.uri) for r in asyncio.run(mcp._list_resources())}
    for ad, dom in registry.DOMAINS.items():
        assert dom.schema.widget_uri in kayitli, f"{ad} → {dom.schema.widget_uri} kayıtsız"


def test_her_domain_en_fazla_bir_tarih_kolonu():
    """Zaman omurgası tek tik sütunu sürer; iki tarih kolonu belirsizdir."""
    for ad, dom in registry.DOMAINS.items():
        tarih = [c for c in dom.schema.columns if c.role == "date"]
        assert len(tarih) <= 1, f"{ad}: {len(tarih)} tarih kolonu"


def test_chip_degerleri_ascii_slug_ile_anahtarlanir():
    """D6 + `tr_lower` tuzağı: slug'lar parser'ın ASCII çıktısı, Türkçe DEĞİL."""
    for ad, dom in registry.DOMAINS.items():
        for c in dom.schema.columns:
            for slug in c.values:
                assert slug.isascii(), f"{ad}.{c.key}: {slug!r} ASCII değil"
                assert slug == slug.lower(), f"{ad}.{c.key}: {slug!r} küçük harf değil"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_buyutme_csse_birakilmaz(path):
    """`text-transform: uppercase` YASAK — Türkçe'de sessizce YANLIŞ üretir.

    CSS büyütmesi `lang`'a bağlıdır; lang eksik/yanlışsa `Nis`→`NIS` ve
    `Deri testi`→`DERI TESTI` olur (doğrusu `NİS`, `DERİ TESTİ`). Ölçüldü:
    Faz 0 önizlemesinde tarayıcıda bu hâliyle göründü. Büyütme JS'te açık
    `toLocaleUpperCase("tr")` ile yapılır — bu, D6'nın ı/i tuzağının CSS hâli.
    """
    src = _kod(path)
    assert "text-transform: uppercase" not in src, (
        f"{path.name}: CSS büyütmesi Türkçe'de `NIS`/`DERI TESTI` üretir; "
        'JS tarafında toLocaleUpperCase("tr") kullanın'
    )


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_turkce_ay_kisaltmalari_dogru(path):
    """Ay adları zaten büyük ve Türkçe doğru sabitlenmeli."""
    src = _src(path)
    if "AYLAR" not in src:
        pytest.skip(f"{path.name} ay kısaltması kullanmıyor")
    for ay in ("NİS", "EKİ", "ŞUB", "AĞU"):
        assert f'"{ay}"' in src, f"{path.name}: {ay} yanlış — Türkçe büyütme bozulmuş"
    for yanlis in ('"NIS"', '"EKI"'):
        assert yanlis not in src, f"{path.name}: {yanlis} — ASCII büyütme sızmış"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_utf8_charset_beyan_edilir(path):
    """Charset yoksa tarayıcı tahmin eder ve Türkçe mojibake olur (`10 kayÄ±t`)."""
    assert '<meta charset="utf-8"' in _src(path), f"{path.name}: charset beyanı yok"


def test_widget_uri_ui_semasinda():
    """`ui://` dışındaki şema host'a widget sinyali VERMEZ."""
    assert schema.TABLE_URI.startswith("ui://")
    for dom in registry.DOMAINS.values():
        assert dom.schema.widget_uri.startswith("ui://")
