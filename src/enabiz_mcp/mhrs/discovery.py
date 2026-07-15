"""MHRS keşfi — SAF mantık: SPA bundle'ından API çağrılarını çıkarma, salt-okunur
sınıflama ve PHI-güvenli rapor üretimi.

Bu modül **ağ yapmaz** ve bir MCP tool'u DEĞİLDİR (`enabiz_mcp.discovery`'nin MHRS
karşılığı). Canlı indirme `scripts/discover_mhrs.py`'dedir.

Tasarım ilkesi: MHRS vatandaş arayüzü bir React/webpack SPA'sidir ve **her API
çağrısı istemci kodunda bir string literal'dir** (canlı build 2.1.405'te 270/270
çağrı yeri; sıfır dinamik URL). Dolayısıyla endpoint evreni, hiçbir kimlik doğrulama
yapmadan ve `/api/`'ye tek bir istek atmadan, yalnız public statik JS okunarak
çıkarılabilir.

E-Nabız keşfinden ayrıldığı yerler (hepsi canlı bundle'da doğrulandı):

- **`/api/` literal'lerde GEÇMEZ.** axios `baseURL="https://prd.mhrs.gov.tr/api/"`
  kurar, çağrılar relatiftir: `.get("vatandas/dil")`. `/api/` arayan bir tarama 142
  ucun 4'ünü bulur. Doğru hedef `API_PREFIXES`.
- **Uçlar main bundle'da değil, lazy chunk'lardadır.** `vatandas-main.js` içinde
  "slot" sıfır kez geçer; randevu API'si yalnız chunk'larda yaşar.
- **Fiil yolun ORTASINDADIR, sonda id vardır** (`kurum/randevu/iptal-et/{hrn}`).
  `enabiz_mcp.discovery._action_segment` gibi son segmente bakmak `{hrn}` döndürür
  ve fiili tamamen kaçırır → burada TÜM yol taranır.
- **HTTP metodu güvenlik sinyali DEĞİLDİR.** MHRS 12 ucu GET ile yazar; en
  çarpıcısı `GET kurum/randevu/ayni-hekimden-randevu-al/{id}` — GET ile randevu alır.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

# --------------------------------------------------------------------------- #
# Sabitler (canlı build 2.1.405'ten doğrulandı)
# --------------------------------------------------------------------------- #
BUNDLE_ORIGIN = "https://prd.mhrs.gov.tr"
BUNDLE_INDEX = "/vatandas/"
API_BASE = "https://prd.mhrs.gov.tr/api/"

# Gerçek API yollarının ilk segmenti. ALLOWLIST'tir, heuristik değil: naif bir
# "slash içeren string" taraması Draft.js'in CSS classname'lerini
# (`public/DraftStyleDefault/block`) API sanır — canlı bundle'da 20 yanlış pozitif.
#
# `kurum-rss/` AYRI bir prefix'tir, `kurum/`'un alt kümesi DEĞİL. Bu allowlist bir
# tur `("vatandas/", "kurum/", "yonetim/")` olarak koştu ve slot arama uçlarının
# İKİSİNİ DE — yani Faz 2'nin tüm çekirdeğini — sessizce düşürdü: `kurum-rss/...`
# hiçbir prefix'le başlamıyordu, eşleşmedi, rapora hiç girmedi. Boşluk yalnız
# "kaçan uç var mı" diye bundle'ı elle tarayınca görüldü; rapor 151 uçla eksiksiz
# GÖRÜNÜYORDU. Allowlist daralttığı için güvenli, ama sessizce daraltıyor: yeni bir
# prefix eklemeden önce `tests/test_mhrs_discovery.py::test_no_unknown_api_prefixes`
# taramasını koştur.
API_PREFIXES = ("vatandas/", "kurum/", "kurum-rss/", "yonetim/")

Verdict = Literal["read", "write", "unknown"]

# Metodla yazma: POST/PUT/DELETE varsayılan olarak yazma sayılır ve asla otomatik
# çağrılmaz. Temkinli bir kural; yanılmanın güvenli yönü budur.
WRITE_METHODS = frozenset({"POST", "PUT", "DELETE"})

# POST ile OKUYAN uçlar — DAR ve ELLE İNCELENMİŞ istisna listesi.
#
# MHRS slot aramayı gövdeli POST ile yapar (filtre nesnesi query string'e sığmıyor).
# Metot kapısı tek başına bunları "write" sayar; `_forbid_write` da onları bloklardı
# — yani Faz 2'nin çekirdek OKUMASI kendi güvenlik kapımıza takılırdı.
#
# Bu bir gevşetme değil, adı adı sayılmış bir istisna: varsayılan hâlâ "POST = yazma".
# Buraya bir uç eklemek insan incelemesi gerektirir; ölçüt "sunucuda durum
# değiştirmiyor mu", "adı okuma gibi mi" DEĞİL. Yazma sözcüğü taşıyan bir yol
# buraya konsa bile `_WRITE_TOKENS` kapısı önce koşar ve yazma damgası kazanır
# (bkz. `classify_mhrs_call` sırası + `test_read_posts_carry_no_write_token`).
_READ_POSTS = frozenset(
    {
        # Kurum/klinik arama — filtre gövdesi (il/ilçe/klinik/kurum/zaman).
        "kurum-rss/randevu/slot-sorgulama/arama",
        # Slot listesi — Faz 2'nin kalbi; seçilen kurum+klinik için boş saatler.
        "kurum-rss/randevu/slot-sorgulama/slot",
    }
)

# GET ile YAZAN uçlar için ad-bazlı denylist. Bunlar olmadan replay randevu alır.
#
# Sınır sınıfı yalnız `-` ve `/`. `_` BİLİNÇLİ olarak dışarıda: aksi halde
# `yonetim/genel/parametre/degeri/RIS_RANDEVU_AL_ADIMI` (bir UI parametresi okuması)
# "al" ile eşleşip yazma sayılırdı.
#
# NOT: `enabiz_mcp.discovery._WRITE_TOKENS` burada KULLANILAMAZ — o bitişik
# `RandevuAl` arar ve MHRS'nin kebab-case'inde körelir:
#     _WRITE_TOKENS.search("randevu-al") -> None
# Bu yüzden fork değil, ayrı ve tire-duyarlı bir denylist.
# `gec`/`don` BİLİNÇLİ olarak yok: tek hedefleri `yetkili-hesaba-gec` ve
# `hesabima-don` idi, ikisi de POST → zaten metotla yakalanıyor. Buna karşılık `gec`
# `slot-sorgulama/en-gec-gun/...` (bir OKUMA, üstelik Faz 2'nin çekirdeği) ile
# eşleşiyordu. Sıfır fayda, gerçek zarar.
_WRITE_TOKENS = re.compile(
    r"(?:^|[-/])(?:"
    r"al|iptal|sil|ekle|kaydet|guncelle|degistir|olustur"
    r"|gizle|kaldir|onay(?:la)?|reddet|bilgilendir|kilitle(?:me)?"
    r"|tekrarla|yenile|gonder"
    r")(?:[-/]|$)",
    re.IGNORECASE,
)

# Okuma sözcükleri — yalnız bunlar güvenle "read" sayılır. Belirsizler "unknown"
# düşer ve replay EDİLMEZ (e-Nabız'daki aynı temkinli duruş).
_READ_TOKENS = re.compile(
    r"(?:^|[-/])(?:"
    r"sorgula(?:ma)?|select-?input|search|getir|liste(?:si)?|gecmisi|arsiv"
    r"|bilgi(?:si|leri)?|by-kodu|degeri|menu|dil|aktif|en-yakin|en-gec-gun"
    r"|uyari|grup|tree|yaklasan|genel-arama|favori|kontrol|goster"
    r"|ekleyebilir-mi|guvenlik-resimleri|sikca-sorulan-sorular"
    r")(?:[-/]|$|\?)",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# Veri yapıları
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ChunkTemplate:
    """`main.js`'teki webpack lazy-chunk yükleyicisinden çıkarılan ad şablonu.

    Canlı örnek: `.p="/vatandas/"` + `.p+"vatandas-"+({}[t]||t)+"-chunk.js?t=178..."`
    → public_path="/vatandas/", prefix="vatandas-", suffix="-chunk.js?t=178..."
    İsim haritası (`{}`) boş olduğu için chunk id doğrudan dosya adına girer.
    """

    public_path: str
    prefix: str
    suffix: str
    name_map: dict[str, str] = field(default_factory=dict)
    referenced_ids: tuple[int, ...] = ()

    def url_for(self, chunk_id: int) -> str:
        """Bir chunk id'si için (origin'e göre relatif) URL üretir."""
        name = self.name_map.get(str(chunk_id), str(chunk_id))
        return f"{self.public_path}{self.prefix}{name}{self.suffix}"


@dataclass(frozen=True)
class MhrsCall:
    """Bundle'da bulunan tek bir axios çağrı yeri."""

    method: str
    path: str  # route şablonu, ör. "kurum/randevu/iptal-et/{p1}"
    source: str  # bulunduğu dosya (ör. "chunk-45")

    @property
    def verdict(self) -> Verdict:
        return classify_mhrs_call(self.method, self.path)


@dataclass(frozen=True)
class MhrsReportRow:
    """PHI-güvenli rapor satırı — yalnız API SÖZLEŞMESİ alanları.

    Bilinçli olarak YOK: byte_size, item_count, liste uzunluğu. Bunlar kullanıcının
    verisinin fonksiyonudur, sözleşmenin değil — commit'lenen bir artefaktta
    kardinalite de PHI'dir. (`build_mhrs_report` bunu davranışsal olarak garanti
    eder; bkz. tests/test_mhrs_discovery.py.)
    """

    method: str
    path: str
    verdict: str
    source: str


# --------------------------------------------------------------------------- #
# index.html / main.js çıkarımı
# --------------------------------------------------------------------------- #
_SCRIPT_SRC_RE = re.compile(r"""<script[^>]*\bsrc=["']([^"']+)["']""", re.IGNORECASE)
_BUILD_VERSION_RE = re.compile(r"Build version:\s*([0-9.]+)")
_PUBLIC_PATH_RE = re.compile(r'\.p\s*=\s*"([^"]*)"')
_CHUNK_TPL_RE = re.compile(
    r'\.p\+"([^"]*)"\+\((\{[^{}]*\})\[\w+\]\|\|\w+\)\+"([^"]*)"'
)
_CHUNK_ID_RE = re.compile(r"\.e\((\d{1,4})\)")
_NAME_MAP_ENTRY_RE = re.compile(r'(\d+)\s*:\s*"([^"]*)"')


def extract_script_srcs(index_html: str) -> list[str]:
    """`index.html`'deki yerel `<script src>` yollarını döndürür (harici host'lar elenir).

    Canlı build'de tek yerel giriş `./vatandas-main.js?v2.1.405`'tir; gtag gibi
    harici script'ler (googletagmanager.com) atılır.
    """
    out: list[str] = []
    for src in _SCRIPT_SRC_RE.findall(index_html):
        if src.startswith(("http://", "https://", "//")):
            continue
        if src not in out:
            out.append(src)
    return out


def extract_build_version(index_html: str) -> str | None:
    """`<!-- [AIV_SHORT] Build version: 2.1.405 ... -->` yorumundan sürümü okur."""
    m = _BUILD_VERSION_RE.search(index_html)
    return m.group(1) if m else None


def extract_chunk_template(main_js: str) -> ChunkTemplate | None:
    """`main.js`'ten lazy-chunk ad şablonunu ve referans verilen id'leri çıkarır.

    Şablon her deploy'da değişir (cache-buster `?t=<ms>`), bu yüzden ASLA sabit
    kodlanmaz — her taramada yeniden okunur.
    """
    tpl = _CHUNK_TPL_RE.search(main_js)
    if not tpl:
        return None
    prefix, raw_map, suffix = tpl.group(1), tpl.group(2), tpl.group(3)

    pp = _PUBLIC_PATH_RE.search(main_js)
    public_path = pp.group(1) if pp else BUNDLE_INDEX

    name_map = dict(_NAME_MAP_ENTRY_RE.findall(raw_map))
    ids = sorted({int(i) for i in _CHUNK_ID_RE.findall(main_js)})

    return ChunkTemplate(
        public_path=public_path,
        prefix=prefix,
        suffix=suffix,
        name_map=name_map,
        referenced_ids=tuple(ids),
    )


# --------------------------------------------------------------------------- #
# axios çağrı çıkarımı
# --------------------------------------------------------------------------- #
# UZUN prefix ÖNCE: `kurum|kurum-rss` sırasıyla motor "kurum-rss/x" için önce `kurum`
# alternatifini dener, ardından gelen `/`'i bulamaz ve ancak backtrack ederek
# `kurum-rss`'e ulaşır. Python re bunu yapar, ama davranışı backtracking'e bağlamak
# gereksiz bir kırılganlık — uzunluğa göre sıralamak eşleşmeyi sıradan bağımsız kılar.
_PREFIX_ALT = "|".join(sorted((p.rstrip("/") for p in API_PREFIXES), key=len, reverse=True))
# `/?` — baştaki slash İSTEĞE BAĞLI. Bundle her iki biçimi de kullanıyor: çoğu çağrı
# relatiftir (`.get("vatandas/dil")`), ama hesap-bilgileri ekranları ve main.js'teki
# dil ucu baştan slash'lı yazılmış (`.put("/vatandas/dil/dil-bilgileri/")`). axios
# ikisini de aynı `baseURL`'e göre çözer, yani AYNI uçturlar. `/?` olmadan 7 uç —
# `parola-degistir` dahil — haritaya hiç girmiyordu.
_CALL_RE = re.compile(
    rf"""\.(get|post|put|delete)\(\s*["'](/?(?:{_PREFIX_ALT})/[^"']*)["']""",
    re.IGNORECASE,
)
# Literal'i izleyen `.concat(...)` zinciri — ara-parametreli route'lar için.
# `.match(js, pos)` ile kullanılır (pos'ta zaten çapalıdır; Python re `\G` desteklemez).
_CONCAT_RE = re.compile(r"\s*\.concat\(")


def _split_args(text: str, start: int) -> tuple[list[str], int]:
    """`(` sonrası argümanları tırnak-duyarlı böler; (args, kapanış+1) döndürür.

    Naif `split(",")` kullanılamaz: `.concat(e,"&mhrsKlinikId=")` gibi çağrılarda
    string literal'in İÇİNDE virgül olabilir.
    """
    args: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: str | None = None
    i = start
    while i < len(text):
        c = text[i]
        if quote:
            buf.append(c)
            if c == "\\" and i + 1 < len(text):
                buf.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
            buf.append(c)
        elif c in "([{":
            depth += 1
            buf.append(c)
        elif c in ")]}":
            if depth == 0 and c == ")":
                args.append("".join(buf).strip())
                return [a for a in args if a], i + 1
            depth -= 1
            buf.append(c)
        elif c == "," and depth == 0:
            args.append("".join(buf).strip())
            buf = []
        else:
            buf.append(c)
        i += 1
    return [a for a in args if a], i


def merge_concat_route(literal: str, args: list[str]) -> str:
    """Literal + `.concat` argümanlarını tek bir route şablonuna birleştirir.

    String literal argümanlar aynen eklenir; değişkenler `{pN}` yer tutucusu olur.
    Sayısal literal'ler aynen korunur — MHRS'de `-1` "hepsi" sentinel'idir ve
    şablonda görünmesi bilgi taşır (canlı: `kurum/kurum/kurum-klinik/il/-1/ilce/`).

    >>> merge_concat_route("kurum/x/il/", ['e', '"/ilce/"', 'a'])
    'kurum/x/il/{p1}/ilce/{p2}'
    """
    out = [literal]
    n = 0
    for arg in args:
        if len(arg) >= 2 and arg[0] in "\"'" and arg[-1] == arg[0]:
            out.append(arg[1:-1])
        elif re.fullmatch(r"-?\d+(?:\.\d+)?", arg):
            out.append(arg)
        else:
            n += 1
            out.append(f"{{p{n}}}")
    return "".join(out)


def extract_calls(js: str, source: str = "") -> list[MhrsCall]:
    """Bir JS dosyasındaki tüm axios çağrılarını (method + route şablonu) çıkarır.

    Method, literal'in hemen SOLUNDAKİ `.get(` / `.post(` / `.put(` / `.delete(`
    bitişikliğinden okunur — canlı build'de bu %100 tutar. `.get(C)` gibi
    değişken-argümanlı eşleşmeler axios değil Map/Set operasyonlarıdır ve
    `API_PREFIXES` allowlist'i sayesinde zaten elenirler.

    (method, path) çiftine göre tekilleştirir.
    """
    calls: list[MhrsCall] = []
    seen: set[tuple[str, str]] = set()

    for m in _CALL_RE.finditer(js):
        method = m.group(1).upper()
        # Baştaki slash NORMALLEŞTİRİLİR: `/vatandas/dil` ile `vatandas/dil` axios'ta
        # aynı uçtur, ama tekilleştirme string'e baktığı için normalleştirilmezse iki
        # ayrı satır olarak rapora düşer ve uç sayısını şişirir.
        literal = m.group(2).lstrip("/")

        # Literal'i izleyen `.concat(...)` zincirini topla.
        args: list[str] = []
        pos = m.end()
        while True:
            cm = _CONCAT_RE.match(js, pos)
            if not cm:
                break
            chunk_args, pos = _split_args(js, cm.end())
            args.extend(chunk_args)

        path = merge_concat_route(literal, args) if args else literal
        key = (method, path)
        if key in seen:
            continue
        seen.add(key)
        calls.append(MhrsCall(method=method, path=path, source=source))

    return calls


# --------------------------------------------------------------------------- #
# Salt-okunur sınıflama
# --------------------------------------------------------------------------- #
def _strip_query(path: str) -> str:
    return path.split("?", 1)[0]


def classify_mhrs_call(method: str, path: str) -> Verdict:
    """Bir MHRS çağrısını 'read' / 'write' / 'unknown' olarak sınıflar.

    Kapılar, SIRAYLA — sıra davranışın parçasıdır:

    1. **Ad**: TÜM yolda (son segmentte değil — MHRS'de fiil ortadadır) bir yazma
       sözcüğü varsa 'write'. Bu kapı ÖNCE koşar ki `_READ_POSTS` istisnası bir
       yazma sözcüğünü asla ezemesin — istisna listesine yanlışlıkla `.../iptal-et`
       konsa bile yazma damgası kazanır.
    2. **Metod**: POST/PUT/DELETE → 'write'; tek çıkış `_READ_POSTS` (gövdeli arama).
    3. **Okuma sözcüğü** → 'read'. Hiçbiri yoksa 'unknown' (temkinli: replay EDİLMEZ).

    GET'in güvenli olduğunu VARSAYMAZ: canlı MHRS'de 12 uç GET ile yazar (`iptal-et`,
    `geri-al`, `gizle`, `onayla`, `reddet`, `bilgilendir` ve en tehlikelisi
    `ayni-hekimden-randevu-al` — GET ile randevu alır). Simetrik olarak POST'un
    yazdığını da varsaymaz: slot arama gövdeli bir OKUMA'dır.
    """
    clean = _strip_query(path)
    if _WRITE_TOKENS.search(clean):
        return "write"
    if method.upper() in WRITE_METHODS:
        return "read" if clean in _READ_POSTS else "write"
    if _READ_TOKENS.search(clean):
        return "read"
    return "unknown"


def is_write(method: str, path: str) -> bool:
    """`classify_mhrs_call(...) == "write"` için kısayol (çalışma-zamanı koruması)."""
    return classify_mhrs_call(method, path) == "write"


# --------------------------------------------------------------------------- #
# PHI-güvenli rapor
# --------------------------------------------------------------------------- #
def build_mhrs_report(rows: list[MhrsReportRow], meta: dict) -> str:
    """Commit'lenebilir, PHI içermeyen Markdown keşif raporu üretir.

    Yalnız API sözleşmesi yazılır: method, route şablonu, verdict, kaynak dosya.
    Kullanıcı verisinin hacmine bağlı HİÇBİR nicelik yazılmaz — `byte_size` /
    `item_count` gibi alanlar kardinalite sızdırır ve bir sağlık hesabında
    kardinalite de PHI'dir.
    """
    write_rows = [r for r in rows if r.verdict == "write"]
    lines: list[str] = []
    lines.append("# Bulgu: MHRS bundle keşif raporu (PHI-güvenli)")
    lines.append("")
    lines.append(
        "> Otomatik üretildi (`scripts/discover_mhrs.py`). Yalnız public statik JS "
        "okunarak çıkarıldı — **kimlik doğrulama YOK, `/api/`'ye istek YOK, PHI YOK**. "
        "Ham bundle `docs/findings/raw/mhrs/`'de (gitignored)."
    )
    lines.append("")
    if meta:
        lines.append("**Özet:** " + " · ".join(f"{k}: {v}" for k, v in meta.items()))
        lines.append("")
    lines.append(
        "> ⚠️ **Yazma uçları aşağıda LİSTELENİR ama keşif tarayıcısı tarafından "
        "ASLA çağrılmaz.** Belgelemek çağırmak değildir. MHRS 12 ucu GET ile yazar "
        "(`iptal-et`, `geri-al`, `ayni-hekimden-randevu-al`), bu yüzden HTTP metodu "
        "güvenlik sinyali olarak kullanılamaz — sınıflama ad-bazlıdır."
    )
    lines.append("")
    lines.append("| Method | Yol (route şablonu) | Verdict | Kaynak |")
    lines.append("|---|---|---|---|")
    for r in sorted(rows, key=lambda x: (x.path, x.method)):
        mark = "🔴 " if r.verdict == "write" else ""
        lines.append(f"| {r.method} | `{r.path}` | {mark}{r.verdict} | {r.source} |")
    lines.append("")
    if write_rows:
        lines.append(f"## Yazma uçları ({len(write_rows)}) — tool ÇAĞIRMAZ")
        lines.append("")
        for r in sorted(write_rows, key=lambda x: x.path):
            lines.append(f"- `{r.method} {r.path}`")
        lines.append("")
    return "\n".join(lines)
