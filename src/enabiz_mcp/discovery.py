"""Keşif (discovery) — SAF mantık: HTML'den veri-yükleme uçlarını çıkarma,
salt-okunur sınıflama, honeypot filtresi ve PHI-güvenli rapor üretimi.

Bu modül **ağ yapmaz** ve bir MCP tool'u DEĞİLDİR (`server.py`'de register
edilmez). Canlı tarama ve giriş `scripts/discover.py`'dedir. Buradaki fonksiyonlar
saf ve test edilebilir olduğu için `tests/test_discover.py` ile doğrulanır.

Tasarım ilkesi: bir sayfanın *kendi* `$.ajax` çağrılarından veri-yükleme ucunu
çıkarırız (sayfadaki `<a href>` linklerini ASLA takip etmeyiz). Yalnızca **okuma**
olarak sınıflanan ve tüm parametre *değerleri* bilinen (boş, yıl, ya da antiforgery
token) uçlar tekrar oynatılır (replay). Yazma/aksiyon uçları hiç çağrılmaz.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from bs4 import BeautifulSoup

# --------------------------------------------------------------------------- #
# Sabitler
# --------------------------------------------------------------------------- #
# Keşfedilecek /Home/* menü sayfaları (slug, path). Ana sayfa dashboard AJAX'ları
# (GetNeyimVarLogin, GetASMBilgileri, Favoriler) için /Home/Index de dahildir.
PAGES: list[tuple[str, str]] = [
    ("alerji", "/Home/Alerjilerim"),
    ("hastalik", "/Home/Hastaliklarim"),
    ("hastalik_takip", "/Home/HastalikTakip"),
    ("asi", "/Home/AsiTakvimi"),
    ("epikriz", "/Home/Epikrizlerim"),
    ("patoloji", "/Home/Patolojilerim"),
    ("ziyaret", "/Home/Ziyaretlerim"),
    ("dokuman", "/Home/Dokumanlarim"),
    ("malzeme_cihaz", "/Home/MalzemeveCihazlarim"),
    ("sigorta", "/Home/Sigortalarim"),
    ("profil", "/Home/ProfilBilgilerim"),
    ("acil_notlar", "/Home/AcilDurumNotlarim"),
    ("organ_bagis", "/Home/OrganBagisBeyan"),
    ("ana_sayfa", "/Home/Index"),
]

# Yıl parametreleri uca göre değişir (bkz. docs/findings/endpoints.md:92).
# Yıl paramları uca göre 4 farklı adla gelir (canlı keşifte doğrulandı):
# baslangicTarihi/bitisTarihi (Tahlil) · baslangicYil/bitisYil (Reçete/İlaç/Epikriz/
# Ziyaret) · startYear/endYear (Rapor) · baslangicYili/bitisYili (Hastalik/Patoloji).
YEAR_START_PARAMS = {"baslangicTarihi", "baslangicYil", "baslangicYili", "startYear"}
YEAR_END_PARAMS = {"bitisTarihi", "bitisYil", "bitisYili", "endYear"}
TOKEN_PARAM = "__RequestVerificationToken"
# Değeri güvenle bilinen enum-tipi paramlar (varsayılan değerleriyle) — bunlar
# replay'i engellemez. activeTab: 0=normal, 1=COVID (bkz. /Tahlil/Index).
KNOWN_ENUM_PARAMS = {"activeTab": "0"}

# Aksiyon (yazma) sözcükleri — bu uçlar ASLA replay edilmez.
_WRITE_TOKENS = re.compile(
    r"(Ekle|Sil|Duzenle|Guncelle|Gizle|Iptal|Kaydet|Onayla|Gonder|Yukle|Beyan"
    r"|Degerlendir|Logout|SetLanguage|SifremiUnuttum|RandevuAl|ManuelRandevu)",
    re.IGNORECASE,
)
# Okuma sözcükleri — yalnızca bunlar güvenle "read" sayılır. Belirsizler ("Goruntule"
# gibi yazma-modalı açabilenler) bilinçli olarak DIŞARIDA bırakılır → "unknown".
_READ_TOKENS = re.compile(
    r"(Index|Get|Listesi|Liste|Rapor|Doldur|Prospektus|KareKod|Gecmis|Favoriler"
    r"|SonHastaneZiyareti|VarMi|Bilgi|Detay|Trend|Covid|Pdf|Link)",
    re.IGNORECASE,
)

Verdict = Literal["read", "write", "unknown"]


# --------------------------------------------------------------------------- #
# Veri yapıları
# --------------------------------------------------------------------------- #
@dataclass
class Endpoint:
    """Bir sayfanın `$.ajax` çağrısından çıkarılan veri-yükleme ucu."""

    url: str
    method: str
    param_names: list[str] = field(default_factory=list)
    container: str | None = None


@dataclass
class ReplayPlan:
    """`plan_replay` sonucu: replay edilecekse `ok=True` ve doldurulmuş `data`."""

    ok: bool
    method: str = "GET"
    data: dict[str, str] = field(default_factory=dict)
    needs_token_body: bool = False
    reason: str = ""


@dataclass
class ReportRow:
    """Keşif taraması satırı.

    ⚠️ Bu yapı PHI-güvenli DEĞİLDİR: `byte_size` ve `row_count` kullanıcının
    verisinin fonksiyonudur (kaç tanısı, kaç aşısı var). Operatör konsolu için
    tutulurlar (`scripts/discover.py` `rows=N` basar), ama **`build_report`
    bunları commit'lenen markdown'a YAZMAZ** — dosyaya giden şey API sözleşmesidir.
    """

    page: str
    endpoint: str
    method: str
    param_names: list[str]
    status: int | None
    byte_size: int | None  # yalnız operatör konsolu — rapora YAZILMAZ (PHI)
    content_type: str
    container: str | None
    row_count: int | None  # yalnız operatör konsolu — rapora YAZILMAZ (PHI)
    verdict: str  # read | write | unknown | honeypot | needs-id:* | auth_dropped | error:*


# --------------------------------------------------------------------------- #
# $.ajax çıkarımı
# --------------------------------------------------------------------------- #
def _balanced(text: str, open_idx: int, open_ch: str, close_ch: str) -> str:
    """`text[open_idx]` == open_ch olan dengeli bloğun *iç* metnini döndürür.

    Basit sayaç; string içi kaçışları göz ardı eder (keşif için yeterli).
    """
    depth = 0
    for i in range(open_idx, len(text)):
        c = text[i]
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i]
    return text[open_idx + 1 :]


_AJAX_RE = re.compile(r"\$\.ajax\s*\(")
_URL_RE = re.compile(r"""url\s*:\s*['"]([^'"?]+)""")
_METHOD_RE = re.compile(r"""(?:method|type)\s*:\s*['"](GET|POST)['"]""", re.IGNORECASE)
_DATA_RE = re.compile(r"data\s*:\s*\{")
_KEY_RE = re.compile(r"""['"]?([A-Za-z_$][\w$]*)['"]?\s*:""")
_SINK_RE = re.compile(r"""\$\(\s*['"](#[\w-]+)['"]\s*\)""")


def extract_ajax_endpoints(html: str) -> list[Endpoint]:
    """Sayfadaki tüm `<script>` bloklarından `$.ajax({...})` çağrılarını çıkarır.

    Her çağrı için url (query string atılır), method (varsayılan POST — jQuery gibi),
    `data` nesnesinin **anahtar adları** (değer YOK → PHI yok) ve `success` içindeki
    ilk `$('#...')` sink container'ı toplanır. (url, method) çiftine göre tekilleştirir.
    """
    soup = BeautifulSoup(html, "html.parser")
    scripts = "\n".join(s.get_text() for s in soup.find_all("script"))

    endpoints: list[Endpoint] = []
    seen: set[tuple[str, str]] = set()
    for m in _AJAX_RE.finditer(scripts):
        paren = scripts.find("(", m.end() - 1)
        if paren == -1:
            continue
        body = _balanced(scripts, paren, "(", ")")

        url_m = _URL_RE.search(body)
        if not url_m:
            continue
        url = url_m.group(1).strip()

        method_m = _METHOD_RE.search(body)
        method = method_m.group(1).upper() if method_m else "POST"

        param_names: list[str] = []
        data_m = _DATA_RE.search(body)
        if data_m:
            brace = body.find("{", data_m.end() - 1)
            obj = _balanced(body, brace, "{", "}")
            param_names = list(_KEY_RE.findall(obj))

        sink_m = _SINK_RE.search(body)
        container = sink_m.group(1) if sink_m else None

        key = (url, method)
        if key in seen:
            continue
        seen.add(key)
        endpoints.append(
            Endpoint(url=url, method=method, param_names=param_names, container=container)
        )
    return endpoints


# --------------------------------------------------------------------------- #
# Sunucu-render container tespiti (AJAX'sız sayfalar: radyoloji/randevu/aşı ...)
# --------------------------------------------------------------------------- #
def detect_containers(html: str) -> list[str]:
    """Veri doğrudan sayfada render edilmişse container seçicilerini döndürür.

    id'li tablolar (`#tbl...`), accordion (`.accordion`/`.accordion-item`) ve tekrar
    eden kart sınıfları (`[class*=CardListe]`). Yalnız *seçici* döner, içerik değil.
    """
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []

    for table in soup.select("table[id]"):
        if table.select_one("tbody tr") or table.select_one("tr"):
            sel = f"#{table['id']}"
            if sel not in found:
                found.append(sel)

    for acc in soup.select(".accordion-item, .accordion"):
        for cls in acc.get("class", []):
            sel = f".{cls}"
            if "accordion" in cls and sel not in found:
                found.append(sel)

    for el in soup.select('[class*="CardListe"], [class*="cardListe"]'):
        for cls in el.get("class", []):
            if "cardliste" in cls.lower():
                sel = f".{cls}"
                if sel not in found:
                    found.append(sel)
    return found


def count_rows(html: str, container: str) -> int:
    """Bir container'daki satır/kart/accordion sayısını sayar (yalnız sayı, içerik yok)."""
    soup = BeautifulSoup(html, "html.parser")
    if container.startswith("#"):
        el = soup.find(id=container[1:])
        if el is None:
            return 0
        rows = el.select("tbody tr") or el.select("tr")
        return len(rows)
    # sınıf seçici → eşleşen eleman sayısı
    return len(soup.select(container))


# --------------------------------------------------------------------------- #
# Salt-okunur sınıflama & honeypot
# --------------------------------------------------------------------------- #
def _action_segment(url: str) -> str:
    path = url.split("?", 1)[0].rstrip("/")
    segs = [s for s in path.split("/") if s]
    return segs[-1] if segs else ""


def classify_action(url: str) -> Verdict:
    """Ucu 'read' / 'write' / 'unknown' olarak sınıflar (aksiyon segmentine göre).

    Yazma sözcüğü varsa her zaman 'write' (öncelikli). Sonra okuma sözcüğü → 'read'.
    Hiçbiri yoksa 'unknown' (temkinli: replay EDİLMEZ).
    """
    action = _action_segment(url)
    if _WRITE_TOKENS.search(action):
        return "write"
    if _READ_TOKENS.search(action):
        return "read"
    return "unknown"


def is_honeypot(url: str) -> bool:
    """Rastgele/obfuske görünen (bot-tuzağı olabilecek) yolları işaretler.

    Ham kanıtlarda tuzak GÖRÜLMEDİ; bu, savunma amaçlı temkinli bir filtredir.
    Controller segmenti alfasayısal değilse ya da olağandışı büyük-harf yoğunluğu
    taşıyorsa (okunur bir sözcüğe benzemiyorsa) tuzak sayılır.
    """
    segs = [s for s in url.split("?", 1)[0].split("/") if s]
    if not segs:
        return True
    for seg in segs[:2]:  # controller + action
        if not re.match(r"^[A-Za-z][A-Za-z0-9]*$", seg):
            return True
        uppers = sum(1 for ch in seg if ch.isupper())
        if len(seg) >= 4 and uppers / len(seg) > 0.4:
            return True
    return False


def plan_replay(ep: Endpoint, start_year: int, end_year: int) -> ReplayPlan:
    """Bir ucun güvenle replay edilip edilemeyeceğini belirler (saf karar).

    Replay yalnızca: (1) 'read' sınıfı, (2) honeypot değil, (3) tüm parametre
    değerleri bilinir (boş, yıl paramı veya antiforgery token). Aksi halde `ok=False`
    ve gerekçe döner (yazma/unknown/honeypot/needs-id).
    """
    if is_honeypot(ep.url):
        return ReplayPlan(ok=False, reason="honeypot")
    verdict = classify_action(ep.url)
    if verdict != "read":
        return ReplayPlan(ok=False, reason=f"not-read({verdict})")

    data: dict[str, str] = {}
    needs_token_body = False
    for p in ep.param_names:
        if p in YEAR_START_PARAMS:
            data[p] = str(start_year)
        elif p in YEAR_END_PARAMS:
            data[p] = str(end_year)
        elif p == TOKEN_PARAM:
            needs_token_body = True
        elif p in KNOWN_ENUM_PARAMS:
            data[p] = KNOWN_ENUM_PARAMS[p]
        else:
            return ReplayPlan(ok=False, reason=f"needs-id:{p}")

    return ReplayPlan(ok=True, method=ep.method, data=data, needs_token_body=needs_token_body)


# --------------------------------------------------------------------------- #
# PHI-güvenli rapor
# --------------------------------------------------------------------------- #
def build_report(rows: list[ReportRow], meta: dict) -> str:
    """Commit'lenebilir, PHI içermeyen Markdown keşif raporu üretir.

    Yalnız **API SÖZLEŞMESİ** yazılır: uç, method, param ADLARI, HTTP durum,
    content-type, container seçici, verdict. Gövde/önizleme YOK.

    **Veri-bağımlı nicelik YOK** — `byte_size` ve `row_count` bilerek yazılmaz.
    Bunlar sözleşmenin değil KULLANICININ fonksiyonudur: `#tblHastaliklarim | 34`
    repo sahibinin gerçek tanı sayısıdır ve bir sağlık hesabında kardinalite de
    PHI'dir. Bu satırlar `fd0b12e`'den beri public GitHub'da duruyordu, üstelik
    "PHI YOK" başlığının altında (invaryant #5 ihlali).

    Ham HTML zaten `docs/findings/raw/`'da (gitignored) — ölçüm gerekirse oradan.

    Kilitleyen test `test_report_contains_no_user_dependent_quantity`: aynı satırlar
    iki farklı veri hacmiyle render edilince çıktı BİREBİR aynı olmalı. Alan-kümesi
    kilidi (`test_discover.py`) bu sınıfı yapısal olarak yakalayamaz — `row_count`
    zaten kümenin içindeydi ve test sonsuza dek yeşil kalıyordu.
    """
    lines: list[str] = []
    lines.append("# Bulgu: Keşif taraması raporu (PHI-güvenli)")
    lines.append("")
    lines.append(
        "> Otomatik üretildi (`scripts/discover.py`). Yalnız API SÖZLEŞMESİ içerir — "
        "hasta değeri YOK, **kayıt sayısı/yanıt boyutu gibi veri-bağımlı nicelik de "
        "YOK** (bunlar kullanıcının verisinin fonksiyonudur). Ham HTML "
        "`docs/findings/raw/`'da (gitignored)."
    )
    lines.append("")
    if meta:
        meta_str = " · ".join(f"{k}: {v}" for k, v in meta.items())
        lines.append(f"**Özet:** {meta_str}")
        lines.append("")
    lines.append("| Sayfa | Uç | Method | Param adları | HTTP | Container | Verdict |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        params = ", ".join(r.param_names) if r.param_names else "—"
        lines.append(
            f"| {r.page} | {r.endpoint} | {r.method} | {params} | "
            f"{r.status if r.status is not None else '—'} | "
            f"{r.container or '—'} | {r.verdict} |"
        )
    lines.append("")
    return "\n".join(lines)
