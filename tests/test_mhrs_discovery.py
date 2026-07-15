"""`enabiz_mcp.mhrs.discovery` — saf bundle çıkarımı ve salt-okunur sınıflama.

En kritik test sınıfı: **GET ile yazan uçlar**. MHRS 11 ucu GET ile yazar
(`iptal-et`, `geri-al`, `gizle`, `onayla`, `reddet`, `bilgilendir`); "GET = okuma"
varsayan bir tarayıcı replay sırasında kullanıcının randevusunu iptal ederdi.

Simetrik iki tuzak da burada kilitli: MHRS **POST ile okur** (slot arama) ve **ad
yalan söyleyebilir** (`ayni-hekimden-randevu-al` randevu ALMAZ — canlıda ölçüldü).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import fixture_html, fixture_text

from enabiz_mcp.mhrs import discovery as m


@pytest.fixture
def bundle() -> str:
    return fixture_text("mhrs_bundle_sample.js")


@pytest.fixture
def calls(bundle: str) -> list[m.MhrsCall]:
    return m.extract_calls(bundle, "sample")


def _paths(calls: list[m.MhrsCall], method: str | None = None) -> set[str]:
    return {c.path for c in calls if method is None or c.method == method}


# --------------------------------------------------------------------------- #
# Sınıflama — projenin can damarı
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "path",
    [
        "kurum/randevu/iptal-et/{p1}",
        "kurum/randevu/iptal-et-hrn-uuid/{p1}/{p2}",
        "kurum/randevu/geri-al/{p1}",
        "kurum/randevu/degisikligi-onayla/{p1}",
        "kurum/randevu/degisikligi-reddet/{p1}",
        "kurum/randevu/cakisma-onay/{p1}",
        "kurum/randevu-ozellik/gizle/{p1}",
        "kurum/randevu-ozellik/gizlilik-kaldir/{p1}",
        "kurum/randevu-talep/bilgilendir/{p1}",
    ],
)
def test_get_that_writes_is_classified_write(path):
    """GET olması bir ucu okuma YAPMAZ — bu uçların hepsi canlı MHRS'de yazar.

    Bu listenin tamamı gerçek build 2.1.405'ten çıkarıldı. Biri "read"e düşerse
    keşif tarayıcısı onu replay eder ve kullanıcının randevusunu iptal eder /
    yenisini alır.
    """
    assert m.classify_mhrs_call("GET", path) == "write"


def test_write_verb_is_found_mid_path_not_last_segment():
    """MHRS'de fiil ORTADA, id SONDA — son segmente bakan sınıflama fiili kaçırır.

    `enabiz_mcp.discovery._action_segment` son segmenti alır; bu yol için `{p1}`
    döner ve `iptal-et` hiç görülmez. MHRS TÜM yolu taramak zorunda.
    """
    from enabiz_mcp import discovery as enabiz

    assert enabiz._action_segment("kurum/randevu/iptal-et/{p1}") == "{p1}"
    assert m.classify_mhrs_call("GET", "kurum/randevu/iptal-et/{p1}") == "write"


def test_mhrs_denylist_catches_kebab_case():
    """MHRS denylist'i kebab-case yakalar — bu, MHRS'nin kendi regex'i olmasının SEBEBİ.

    e-Nabız'ın denylist'i bitişik `RandevuAl` arar; MHRS'nin tüm isimlendirmesi
    kebab-case olduğu için orada körelir. Bu test yalnız MHRS tarafını kilitler
    (e-Nabız'ın davranışını assert ETMEZ — orası düzelirse burası kırılmasın).
    """
    assert m._WRITE_TOKENS.search("randevu-al") is not None
    assert m.classify_mhrs_call("GET", "kurum/randevu/uydurma-randevu-al/{p1}") == "write"


def test_verified_read_beats_the_name_gate():
    """`ayni-hekimden-randevu-al` randevu ALMAZ — CANLIDA ölçüldü, ada rağmen 'read'.

    Bu uç uzun süre "MHRS'nin en tehlikeli ucu: GET ile randevu alır" diye
    belgelendi (CLAUDE.md, mhrs.md, testler, rapor). Yanlıştı — ada inanıldı,
    ölçülmedi. Canlı: yalnız arama kriterlerini döndürüyor
    (`{mhrsKurumId, mhrsKlinikId, mhrsHekimId, mhrsIlId, fkMuayeneYeriId, aksiyonId}`)
    ve aktif randevu listesi öncesi/sonrası AYNI kalıyor.
    """
    assert m.classify_mhrs_call("GET", "kurum/randevu/ayni-hekimden-randevu-al/{p1}") == "read"


def test_verified_read_is_scoped_to_the_measured_method():
    """İstisna (METOD, yol) çiftidir — ölçüm bir metoda aittir.

    `GET .../x`in yazmadığını ölçmek `POST .../x`in de yazmadığını GÖSTERMEZ.
    Yol-bazlı bir liste ölçülmemiş metotlara sessizce okuma damgası verirdi.
    """
    assert m.classify_mhrs_call("GET", "kurum/randevu/ayni-hekimden-randevu-al/{p1}") == "read"
    assert m.classify_mhrs_call("POST", "kurum/randevu/ayni-hekimden-randevu-al/{p1}") == "write"


def test_verified_reads_do_not_leak_to_similar_paths():
    """İstisna çapalıdır — benzeyen bir yol ya da alt yol ondan faydalanamaz."""
    assert m.classify_mhrs_call("GET", "kurum/randevu/ayni-hekimden-randevu-al") == "write"
    assert m.classify_mhrs_call("GET", "kurum/randevu/baska-hekimden-randevu-al/{p1}") == "write"
    # Alt yola sızmamalı:
    assert m.classify_mhrs_call("GET", "kurum/randevu/ayni-hekimden-randevu-al/1/sil") == "write"


def test_verified_read_matches_both_template_and_concrete_path():
    """Sınıflandırıcı İKİ bağlamda koşar — ikisinde de tutmalı.

    Keşif route ŞABLONU verir (`…/{p1}`), çalışma-zamanı kapısı SOMUT yol
    (`…/3KNBUGS`). İlk sürüm düz string olarak şablonu tutuyordu: bu testin şablon
    hâli GEÇİYORDU ama canlı çağrı `WriteNotAllowed` ile patladı. Tek bağlamı
    sınayan bir test, iki bağlamlı bir fonksiyonu kanıtlamaz.
    """
    tpl = "kurum/randevu/ayni-hekimden-randevu-al/{p1}"
    somut = "kurum/randevu/ayni-hekimden-randevu-al/3KNBUGS"
    assert m.classify_mhrs_call("GET", tpl) == "read"
    assert m.classify_mhrs_call("GET", somut) == "read"


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
def test_non_get_methods_are_write_by_default(method):
    """POST/PUT/DELETE VARSAYILAN olarak yazma — adı okuma gibi görünse bile.

    `uyelik/kontrol` bir sorgudur ve `kontrol` bir okuma sözcüğüdür; yine de yazma
    sayılır, çünkü `_READ_POSTS` allowlist'inde DEĞİL. Metot kapısının temkinli
    varsayılanı budur; istisna adı adına incelenerek verilir, ada bakıp tahminle değil.
    """
    assert m.classify_mhrs_call(method, "vatandas/uyelik/kontrol") == "write"


def test_slot_search_posts_are_read_despite_post_method():
    """Gövdeli POST arama OKUMA'dır — Faz 2'nin çekirdeği buna bağlı.

    Regresyon: metot kapısı tek başına bu ikisini "write" sayıyordu, `_forbid_write`
    de onları bloklardı — yani kendi güvenlik kapımız Faz 2'nin okuma yolunu
    kapatıyordu. `slot-sorgulama/slot` boş saatleri LİSTELER, randevu ALMAZ
    (randevu `kurum/randevu/randevu-ekle` ile alınır ve o yazma olarak KALIR).
    """
    assert m.classify_mhrs_call("POST", "kurum-rss/randevu/slot-sorgulama/arama") == "read"
    assert m.classify_mhrs_call("POST", "kurum-rss/randevu/slot-sorgulama/slot") == "read"
    # Asıl yazma ucu istisnadan ETKİLENMEZ:
    assert m.classify_mhrs_call("POST", "kurum/randevu/randevu-ekle") == "write"


def test_read_posts_carry_no_write_token():
    """`_READ_POSTS`'taki hiçbir yol yazma sözcüğü taşımamalı — allowlist'in koruması.

    Ad kapısı metot kapısından ÖNCE koşar, yani bu invaryant bozulsa bile yol yine
    "write" sınıflanır (istisna ezilemez). Test yine de var: sessiz güvenliğe değil,
    listenin bilinçli tutulduğuna dair bir alarm.
    """
    offenders = [p for p in m._READ_POSTS if m._WRITE_TOKENS.search(p)]
    assert not offenders, f"_READ_POSTS'ta yazma sözcüğü: {offenders}"


def test_read_posts_are_reachable_by_the_extractor():
    """Allowlist'teki her yol çıkarıcının prefix'lerinden biriyle başlamalı.

    Aksi halde uç rapora hiç girmez ve `_READ_POSTS` girdisi ÖLÜ config olur —
    tam olarak `kurum-rss/` ile yaşanan hata: istisna anlamlı, ama uç görünmez.
    """
    for path in m._READ_POSTS:
        assert path.startswith(m.API_PREFIXES), f"{path} hiçbir API_PREFIXES ile başlamıyor"


def test_write_token_gate_runs_before_method_gate():
    """Sıra davranıştır: yazma sözcüğü, `_READ_POSTS` istisnasını EZEMEZ.

    Savunma katmanı — allowlist'e yanlışlıkla bir yazma ucu konursa yazma kazansın.
    """
    assert m.classify_mhrs_call("POST", "kurum-rss/randevu/iptal-et/{p1}") == "write"


def test_underscore_constant_with_AL_is_not_write():
    """`RIS_RANDEVU_AL_ADIMI` bir UI parametresi OKUMASI — "AL" içerse de yazma değil.

    Sınır sınıfı `_` içerseydi bu uç yazma sayılır ve gereksizce kilitlenirdi.
    """
    p = "yonetim/genel/parametre/degeri/RIS_RANDEVU_AL_ADIMI"
    assert m.classify_mhrs_call("GET", p) == "read"


def test_slot_sorgulama_is_read_not_write():
    """`en-gec-gun` yazma DEĞİL — regresyon: "gec" token'ı buna çarpıyordu.

    slot-sorgulama Faz 2'nin çekirdek okuma ucu; yazma damgası yerse kullanılamaz.
    """
    for p in (
        "kurum/randevu/slot-sorgulama/randevu-bilgileri?fkSlotId={p1}",
        "kurum/randevu/slot-sorgulama/en-gec-gun/by-aksiyon?aksiyonId={p1}",
        "kurum/randevu/slot-sorgulama/en-gec-gun/by-aksiyon-klinik?aksiyonId={p1}&mhrsKlinikId={p2}",
    ):
        assert m.classify_mhrs_call("GET", p) == "read", p


def test_unknown_when_no_token_matches():
    """Hiçbir sözcük eşleşmiyorsa 'unknown' — replay EDİLMEZ (temkinli)."""
    assert m.classify_mhrs_call("GET", "vatandas/aydinlatma-metni") == "unknown"


def test_query_string_does_not_leak_into_classification():
    """Sınıflama `?` öncesine bakar — query değeri fiil sanılmamalı."""
    assert m.classify_mhrs_call("GET", "kurum/genel-arama?q=iptal-et") == "read"


# --------------------------------------------------------------------------- #
# Çağrı çıkarımı
# --------------------------------------------------------------------------- #
def test_extracts_plain_literal_calls(calls):
    assert ("GET", "vatandas/dil") in {(c.method, c.path) for c in calls}
    assert ("POST", "kurum/randevu/randevu-ekle") in {(c.method, c.path) for c in calls}
    assert ("DELETE", "kurum/randevu/slot-kilitleme") in {(c.method, c.path) for c in calls}


def test_merges_concat_chain_into_route_template(calls):
    """`.concat` zinciri tam route şablonuna birleşir — ara parametreler dahil."""
    assert (
        "kurum/kurum/kurum-klinik/il/{p1}/ilce/{p2}/kurum/{p3}/klinik/{p4}/ana-kurum/select-input"
        in _paths(calls)
    )


def test_numeric_sentinel_is_preserved(calls):
    """`-1` ("hepsi") sabit kalır — yer tutucuya çevrilirse bilgi kaybolur."""
    assert "kurum/kurum/muayene-yeri/ana-kurum/-1/kurum/{p1}/klinik/{p2}/select-input" in _paths(
        calls
    )


def test_query_string_inside_literal_survives(calls):
    """Query string literal'in İÇİNDEyse korunur (virgül-güvenli arg bölme)."""
    assert (
        "kurum/randevu/slot-sorgulama/en-gec-gun/by-aksiyon-klinik?aksiyonId={p1}&mhrsKlinikId={p2}"
        in _paths(calls)
    )


def test_draftjs_classnames_are_not_extracted(calls):
    """`public/DraftStyleDefault/*` API DEĞİL — prefix allowlist onu eler.

    Canlı bundle'da 20 yanlış pozitif; naif "slash içeren string" heuristiği kirli.
    """
    assert not [p for p in _paths(calls) if "DraftStyle" in p or p.startswith("public/")]


def test_map_set_operations_are_not_extracted(calls):
    """`.delete(e.pointerId)` / `.get(t.key)` axios değil — allowlist eler."""
    assert not [p for p in _paths(calls) if "pointerId" in p or p in {"key", "id"}]


def test_kurum_rss_prefix_is_extracted(calls):
    """`kurum-rss/` uçları çıkarılmalı — allowlist bir tur bunları sessizce düşürdü.

    `kurum-rss` ile `kurum` KARDEŞ prefix'lerdir. Allowlist `"kurum/"` istediği için
    `kurum-rss/...` hiçbir alternatifle eşleşmedi; iki uç da rapora hiç girmedi ve
    151 satırlık rapor EKSİKSİZ göründü. Kaçan tam olarak Faz 2'nin çekirdeğiydi.
    """
    found = {(c.method, c.path) for c in calls}
    assert ("POST", "kurum-rss/randevu/slot-sorgulama/arama") in found
    assert ("POST", "kurum-rss/randevu/slot-sorgulama/slot") in found


def test_leading_slash_calls_are_extracted_and_normalised(calls):
    """`/vatandas/x` ile `vatandas/x` AYNI uçtur — çıkarılmalı ve normalleştirilmeli.

    İkinci gerçek kaçak: çıkarıcı literalin prefix'le BAŞLAMASINI şart koşuyordu,
    baştan slash'lı 7 uç haritaya hiç girmedi — biri `PUT .../parola-degistir`, yani
    haritada görünmeyen bir parola değiştirme ucu.

    Normalleştirme ayrıca şart: aksi halde iki yazım aynı ucu iki satıra bölerdi.
    """
    found = {(c.method, c.path) for c in calls}
    assert ("GET", "vatandas/hesap-bilgileri/tema-bilgileri") in found
    assert ("PUT", "vatandas/hesap-bilgileri/parola-degistir") in found
    # Baştaki slash HİÇBİR yolda kalmamalı:
    assert not [p for p in _paths(calls) if p.startswith("/")]


def test_prefix_alternation_is_order_independent():
    """`kurum` alternatifi `kurum-rss`'i gölgelememeli — sıraya bel bağlama.

    Python re backtrack ettiği için sıralamasız da çalışır; bu test o davranışa
    değil, SONUCA bağlanır: hangi sırada yazılırsa yazılsın uzun prefix eşleşir.
    """
    assert m._CALL_RE.search('.post("kurum-rss/randevu/slot-sorgulama/slot",e)')
    assert m._CALL_RE.search('.post("kurum/randevu/randevu-ekle",a)')


#: Yol gibi görünen ama API OLMAYAN prefix'ler — Draft.js CSS classname'leri.
_NON_API_PREFIXES = {"public"}


def test_no_unknown_api_prefixes(bundle):
    """Fixture'da `API_PREFIXES` dışında yol-benzeri bir literal kalmamalı.

    Bu, `kurum-rss` hatasının SINIFINI hedefleyen bekçi: allowlist güvenlidir çünkü
    daraltır, ama SESSİZCE daraltır — düşen uç hiçbir yerde raporlanmaz. Burada
    çıkarıcının dar regex'i değil, GENEL bir "prefix/..." deseni taranır; ikisinin
    farkı allowlist'in kör noktasıdır.

    SINIRI: yalnız fixture'ı korur, canlı bundle'ı değil. Canlı denetim tarama
    zamanında yapılır — `discover_mhrs.py::audit_unknown_prefixes` her koşuda
    allowlist dışı prefix görürse yüksek sesle uyarır.
    """
    # `/?` — script'teki `_GENERIC_CALL_RE` ile AYNI olmalı. Denetim deseni
    # çıkarıcının kör noktasını taşırsa hiçbir şey bulmaz; bu tam olarak bir kez
    # yaşandı (baştan slash'lı 7 uç ikisinden de kaçtı).
    generic = re.compile(
        r"""\.(?:get|post|put|delete)\(\s*["']/?([a-z][a-z0-9-]*)/""", re.IGNORECASE
    )
    seen = {mm.group(1).lower() for mm in generic.finditer(bundle)}
    known = {p.rstrip("/") for p in m.API_PREFIXES} | _NON_API_PREFIXES
    unknown = seen - known
    assert not unknown, (
        f"allowlist dışı prefix(ler): {sorted(unknown)} — API ise API_PREFIXES'e ekle, "
        "değilse _NON_API_PREFIXES'e. Sessizce düşürme."
    )


def test_calls_are_deduplicated(bundle):
    doubled = m.extract_calls(bundle + bundle, "sample")
    once = m.extract_calls(bundle, "sample")
    assert len(doubled) == len(once)


def test_merge_concat_route_placeholders():
    merged = m.merge_concat_route("kurum/x/il/", ["e", '"/ilce/"', "a"])
    assert merged == "kurum/x/il/{p1}/ilce/{p2}"


# --------------------------------------------------------------------------- #
# index.html / chunk şablonu
# --------------------------------------------------------------------------- #
def test_extract_script_srcs_drops_external_hosts():
    """gtag gibi harici script'ler indirilmez — yalnız yerel bundle."""
    srcs = m.extract_script_srcs(fixture_html("mhrs_index_sample"))
    assert "./vatandas-main.js?v9.9.999" in srcs
    assert not [s for s in srcs if "googletagmanager" in s]


def test_extract_build_version():
    assert m.extract_build_version(fixture_html("mhrs_index_sample")) == "9.9.999"


def test_extract_chunk_template(bundle):
    tpl = m.extract_chunk_template(bundle)
    assert tpl.public_path == "/vatandas/"
    assert tpl.url_for(45) == "/vatandas/vatandas-45-chunk.js?t=1700000000000"
    # `.e(N)` referansları toplanır — ama TAM küme DEĞİLdir (canlı: 14 referans, 70 chunk),
    # bu yüzden tarayıcı aralık taraması yapar. Bkz. scripts/discover_mhrs.py.
    assert set(tpl.referenced_ids) >= {0, 19, 45}


def test_chunk_template_missing_returns_none():
    """Şablon bulunamazsa None — sessizce yanlış bir şablon UYDURMA (invaryant #2)."""
    assert m.extract_chunk_template("var x = 1;") is None


# --------------------------------------------------------------------------- #
# PHI: rapor
# --------------------------------------------------------------------------- #
def test_report_ignores_data_volume():
    """Rapor kullanıcı verisinin HACMİNDEN bağımsız olmalı.

    Emsaldeki hata tam buydu: `docs/findings/discovery-report.md` `row_count=34`
    yazıyor ve o 34 repo sahibinin gerçek tanı sayısı. Alan-kümesi kilidi bu sınıfı
    yakalayamaz (`row_count` zaten kümenin içindeydi) — davranış testi gerekir.
    """
    rows = [m.MhrsReportRow(method="GET", path="vatandas/dil", verdict="read", source="c1")]
    a = m.build_mhrs_report(rows, meta={"endpoints": 1})
    b = m.build_mhrs_report(rows, meta={"endpoints": 1})
    assert a == b
    # Rapor satırı hiçbir nicelik alanı taşımıyor
    assert not {"byte_size", "item_count", "row_count"} & set(
        m.MhrsReportRow.__dataclass_fields__
    )


def test_report_marks_write_endpoints():
    rows = [
        m.MhrsReportRow(
            method="GET", path="kurum/randevu/iptal-et/{p1}", verdict="write", source="c"
        ),
        m.MhrsReportRow(method="GET", path="vatandas/dil", verdict="read", source="c"),
    ]
    out = m.build_mhrs_report(rows, meta={})
    assert "Yazma uçları (1)" in out
    assert "ASLA çağrılmaz" in out


# --------------------------------------------------------------------------- #
# Ağsızlık — bu modül asla istek atmamalı
# --------------------------------------------------------------------------- #
def test_mhrs_discovery_module_is_network_free():
    """Saf modül ağ kütüphanesi import ETMEMELİ (canlı indirme scripts/'te).

    Predicate dosyanın KENDİSİNE bakar; "src/ ağacında prd.mhrs.gov.tr geçmesin"
    gibi bir test bu dosyada ilk günden kırmızı olurdu (sabitler burada yaşıyor).
    """
    src = Path(m.__file__).read_text(encoding="utf-8")
    code = re.sub(r'""".*?"""', "", src, flags=re.S)
    assert not re.search(r"^\s*(import|from)\s+(httpx|requests|urllib|socket)", code, re.M)
