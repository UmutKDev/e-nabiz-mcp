"""Commit'lenen HER dosyada sır/kimlik taraması — doküman, kaynak, test, fixture.

`scripts/discover.py:257` yalnız KENDİ ürettiği rapora TCKN tripwire'ı uygular. Elle
yazılan her şey — bulgu dokümanları, testler, fixture'lar — o yoldan geçmez; "gerçek
değer yazma" oraya kadar sadece bir KONVANSİYONDU.

Bu testin kapsamı bilerek geniş: ilk hâli yalnız `docs/`'u tarıyordu ve gerçek bir
sızıntıyı kaçırdı — `tests/test_mhrs_auth.py`'ye canlı bir `enabizToken` ve kişiye
özel bir ID, üstelik "SENTETİK" yorumuyla kopyalanmıştı. Sır nereye düşerse düşsün
repo public; tarama da öyle olmalı.

Kapsam dışı: kardinalite sızıntısı (ör. `row_count=34` = gerçek tanı sayısı). Onu
`build_report`'un davranış testi kilitler — bu test yapısal sırlara bakar.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SELF = Path(__file__).name

# Taranan ağaçlar. `docs/findings/raw/` gitignored ve tanımı gereği PHI — taranmaz.
_SCAN = [
    (_REPO / "docs", "*.md"),
    (_REPO / "src", "*.py"),
    (_REPO / "scripts", "*.py"),
    (_REPO / "tests", "*.py"),
    (_REPO / "tests" / "fixtures", "*"),
]
_SKIP_PARTS = {"raw", "samples", "__pycache__"}

_PATTERNS: dict[str, re.Pattern] = {
    # JWT: header.payload.signature — `eyJ` base64'te `{"` demektir.
    "JWT": re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    "UUID": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE
    ),
    # TCKN: 11 hane, 0 ile başlamaz.
    "TCKN": re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)"),
    "Bearer": re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"),
    # ASP.NET oturum/antiforgery çerez değerleri.
    "AspNetCookie": re.compile(r"CfDJ8[A-Za-z0-9_%+/-]{16,}"),
    # WAF çerezi (SAGLIK<hex>=<uzun hex>).
    "WafCookie": re.compile(r"SAGLIK[0-9a-f]{6,}=[0-9a-f]{20,}", re.IGNORECASE),
}

# Testlerin uydurma UUID'leri: her tire-grubu TEK bir karakterin tekrarı
# (`00000000-1111-2222-3333-444444444444`). Gerçek bir UUID pratikte böyle olmaz.
# Allowlist DAR: "sentetik" YORUMUNA güvenmek tam da kaçırdığımız hataydı — yapıya
# güveniyoruz, iddiaya değil.
_LOW_ENTROPY_UUID = re.compile(
    r"\b(\w)\1{7}-(\w)\2{3}-(\w)\3{3}-(\w)\4{3}-(\w)\5{11}\b", re.IGNORECASE
)


def _scanned_files() -> list[Path]:
    out: list[Path] = []
    for root, glob in _SCAN:
        if not root.exists():
            continue
        for p in root.rglob(glob):
            if not p.is_file() or p.name == _SELF:
                continue
            if _SKIP_PARTS & set(p.relative_to(_REPO).parts):
                continue
            if p not in out:
                out.append(p)
    return out


def _is_allowed(kind: str, value: str) -> bool:
    return kind == "UUID" and bool(_LOW_ENTROPY_UUID.fullmatch(value))


def test_scan_actually_covers_the_tree():
    """Test boşlukta geçmesin: gerçekten dosya taradığını kanıtla.

    Ayrıca kapsamın DARALMASINA karşı koruma — bu testin ilk hâli yalnız docs/'u
    tarıyordu ve tests/'teki gerçek bir sızıntıyı kaçırdı.
    """
    files = _scanned_files()
    names = {p.name for p in files}
    assert len(files) >= 40, f"beklenenden az dosya tarandı: {len(files)}"
    for required in ("mhrs.md", "auth.py", "discover_mhrs.py", "test_mhrs_auth.py"):
        assert required in names, f"{required} taranmıyor — kapsam daralmış"


@pytest.mark.parametrize("kind", sorted(_PATTERNS))
def test_no_secrets_in_committed_files(kind: str):
    """Commit'lenen hiçbir dosya yapısal sır/kimlik içermemeli."""
    pattern = _PATTERNS[kind]
    hits: list[str] = []
    for path in _scanned_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for m in pattern.finditer(text):
            if _is_allowed(kind, m.group(0)):
                continue
            line = text[: m.start()].count("\n") + 1
            # Bulunan değeri BASMA — yerini bas. Aksi halde test çıktısı sırrı sızdırır.
            hits.append(f"{path.relative_to(_REPO)}:{line}")
    assert not hits, f"{kind} kalıbı commit'lenen dosyada bulundu: {hits}"


def test_patterns_actually_match_known_shapes():
    """Kalıplar gerçekten çalışıyor mu — parça parça kurulmuş SAHTE örneklerle.

    Değerler literal YAZILMAZ (yoksa bu dosya kendi taramasını tetiklerdi; dosya
    zaten hariç ama alışkanlık olarak da doğrusu bu).
    """
    # İmza da uzun olmalı — gerçek JWT imzaları uzundur, kalıp {8,} istiyor.
    assert _PATTERNS["JWT"].search(
        "ey" + "J0eXAiOiJKV1Qi" + "." + "eyJzdWIiOiJmYWtlIn0" + "." + "c2lnbmF0dXJlLWZha2U"
    )
    assert _PATTERNS["UUID"].search("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    assert _PATTERNS["TCKN"].search("12345678901")
    assert _PATTERNS["Bearer"].search("Authorization: Bearer abcdefghijklmnop123")
    assert _PATTERNS["AspNetCookie"].search("Cf" + "DJ8" + "BS1V_h9CGRKiEJ6FCJadT8")


def test_placeholders_do_not_trip_the_scan():
    """Dokümanların kullandığı yer tutucu stili eşleşmemeli."""
    for p in _PATTERNS.values():
        assert not p.search("<uuid> <jwt> <kişiye-özel-id> <...> Bearer <jwt>")


def test_low_entropy_uuid_allowlist_is_narrow():
    """Allowlist yalnız açıkça uydurma UUID'leri geçirmeli — gerçek olanı DEĞİL."""
    assert _LOW_ENTROPY_UUID.fullmatch("00000000-1111-2222-3333-444444444444")
    assert not _LOW_ENTROPY_UUID.fullmatch("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
