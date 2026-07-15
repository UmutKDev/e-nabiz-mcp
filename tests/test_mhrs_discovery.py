"""`enabiz_mcp.mhrs.discovery` — saf bundle çıkarımı ve salt-okunur sınıflama.

En kritik test sınıfı: **GET ile yazan uçlar**. MHRS 12 ucu GET ile yazar; en
tehlikelisi `ayni-hekimden-randevu-al` GET ile randevu ALIR. "GET = okuma" varsayan
bir tarayıcı replay sırasında kullanıcıya gerçek randevu yazardı.
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
        "kurum/randevu/ayni-hekimden-randevu-al/{p1}",
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


def test_mhrs_denylist_catches_kebab_case_randevu_al():
    """MHRS denylist'i kebab-case yakalar — bu, MHRS'nin kendi regex'i olmasının SEBEBİ.

    e-Nabız'ın denylist'i bitişik `RandevuAl` arar; MHRS'nin tüm isimlendirmesi
    kebab-case olduğu için orada körelir. Bu test yalnız MHRS tarafını kilitler
    (e-Nabız'ın davranışını assert ETMEZ — orası düzelirse burası kırılmasın).
    """
    assert m.classify_mhrs_call("GET", "kurum/randevu/ayni-hekimden-randevu-al/{p1}") == "write"


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
def test_non_get_methods_are_always_write(method):
    """POST/PUT/DELETE her zaman yazma — adı ne olursa olsun (temkinli)."""
    assert m.classify_mhrs_call(method, "vatandas/uyelik/kontrol") == "write"


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
