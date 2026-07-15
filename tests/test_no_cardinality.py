"""Commit'lenen dosyalarda KARDİNALİTE taraması — sızıntının sayı hâli.

Bir sağlık hesabında "kaç kayıt var" sorusunun cevabı da PHI'dir: tanı ADI olmadan
bile "onlarca tanı, onlarca ilaç, on yıllık takip" bir sağlık ayak izidir. Referans
dışı sonuç ADEDİ ise doğrudan klinik bulgudur.

Bu test DÖRT gerçek sızıntının regresyonu — hepsi "PHI YOK" iddia eden başlıkların
altındaydı ve üç ayrı tarama turunda ancak tamamı bulunabildi:

- `docs/findings/discovery-report.md` → container'dan sonra çıplak sayı
  (canlı kimlikli taramadan üretilmiş gerçek tanı sayısı)
- `docs/findings/data-models.md`      → "Doğrulama (canlı): <yıl>–<yıl> → <n> rapor,
  <n> test" ve 10 benzeri; ayrıca "<n> normal / <n> ref_disi" (klinik)
- `docs/STATUS.md`                    → başlığı itiraf eden, etiketli tam envanter
- `src/enabiz_mcp/tools/labs.py` + `_common.py` → kod yorumlarında sayılar

Neden ayrı bir test: `test_discover.py`'deki alan-kümesi kilidi bu sınıfı yapısal
olarak yakalayamaz (`row_count` zaten kümenin içindeydi), ve `build_report`'un
davranış testi yalnız ÜRETİLEN raporu korur — elle yazılan dokümanları değil.

Doğrulama notları **nitel** yazılır: "onlarca kayıt, tüm alanlar dolu".

Fixture'lar UYDURMA sayı kullanır: kalıbı sınamak için ŞEKİL yeterlidir, gerçek
değere ihtiyaç yoktur — ve gerçek değeri test dosyasına yazmak aynı sızıntıdır.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SELF = Path(__file__).name

# `docs/findings/raw/` gitignored ve tanımı gereği PHI — taranmaz.
_SKIP_PARTS = {"raw", "samples", "__pycache__"}
_SCAN = [(_REPO / "docs", "*.md"), (_REPO / "src", "*.py"), (_REPO / "scripts", "*.py")]

_UNIT = (
    r"(?:kay[ıi]t|ziyaret|rapor|test|nokta|tan[ıi]|sonu[çc]|a[şs][ıi]"
    r"|ila[çc]|re[çc]ete|randevu|[çc]al[ıi][şs]ma|vaka)"
)

_CARDINALITY = re.compile(
    # "Canlı: <n> kayıt" · "canlı veri <n> rapor" (araya kelime girebilir)
    rf"(?:Canl[ıi][^.\n]{{0,24}}?\d+\s*{_UNIT}"
    # "→ <n> rapor" · ", <n> test" · "/ <n> test"
    rf"|[→/,]\s*\d+\s*{_UNIT}\b"
    # "<n> kayıt gözlendi" · "<n> sonuç döndürebiliyor"
    rf"|\d+\s*{_UNIT}\s*(?:g[öo]zlendi|bulundu|d[öo]nd[üu]|d[öo]nd[üu]rebiliyor|var)"
    # "<n>/<n> dolu" · "<n>/<n>;"  (data-models'daki "391/391" şekli)
    r"|\d+/\d+\s*(?:dolu|;)"
    # "<n> normal / <n> ref_disi" — KLİNİK: kaç sonucun referans dışı olduğu
    r"|\d+\s*normal\s*/\s*\d+"
    # "tanı N · reçete N ·" — STATUS.md'nin etiketli envanter şekli
    rf"|{_UNIT}\s+\d+\s*·"
    # "(<n> test ≈ 14.7k token)"
    rf"|\(\s*\d+\s*{_UNIT}\s*≈"
    # "Canlı: <n> KB geçerli PDF" — PDF boyutu rapor uzunluğunun fonksiyonu
    r"|Canl[ıi][^.\n]{0,24}?\d+\s*[KMG]B"
    # Etiketin kendisi — bir daha asla
    r"|Canl[ıi] kay[ıi]t say[ıi]lar[ıi]"
    # "<yıl>–<yıl>" — takip süresini ele verir. `year_range: 2021-2026` HARİÇ:
    # o tarayıcının sorgu penceresi (`this_year - 5`, discover.py:211), veriye bağlı
    # DEĞİL — sıfır kaydı olan kullanıcı da aynısını görür.
    r"|(?<!year_range: )\b(?:19|20)\d{2}\s*[–—-]\s*(?:19|20)\d{2}\b)",
    re.IGNORECASE,
)


def _scanned() -> list[Path]:
    out: list[Path] = []
    for root, glob in _SCAN:
        if not root.exists():
            continue
        for p in root.rglob(glob):
            if not p.is_file() or p.name == _SELF:
                continue
            if _SKIP_PARTS & set(p.relative_to(_REPO).parts):
                continue
            out.append(p)
    return out


def test_scan_actually_covers_the_tree():
    """Test boşlukta geçmesin: gerçekten dosya taradığını kanıtla.

    Kapsam DARALMASINA karşı da koruma — bu sızıntı üç turda bulunabildi çünkü ilk
    iki tarama dar kapsamlıydı (`STATUS.md`'ye hiç bakılmamıştı).
    """
    names = {p.name for p in _scanned()}
    assert len(names) >= 20, f"beklenenden az dosya tarandı: {len(names)}"
    for required in ("data-models.md", "discovery-report.md", "STATUS.md", "labs.py", "_common.py"):
        assert required in names, f"{required} taranmıyor — kapsam daralmış"


def test_no_live_cardinality_in_committed_files():
    """Commit'lenen doküman/kaynak kullanıcının KAYIT SAYISINI söylememeli."""
    hits: list[str] = []
    for p in _scanned():
        text = p.read_text(encoding="utf-8")
        for m in _CARDINALITY.finditer(text):
            line = text[: m.start()].count("\n") + 1
            hits.append(f"{p.relative_to(_REPO)}:{line} → {m.group(0)!r}")
    assert not hits, (
        "canlı kardinalite (PHI) commit'lenen dosyada — doğrulama notlarını NİTEL yaz "
        '("onlarca kayıt, tüm alanlar dolu"):\n  ' + "\n  ".join(hits)
    )


# Fixture'lar PROGRAMATİK kurulur: literal'de rakam yoksa bir redaksiyon geçişi
# (git filter-repo blob-callback) bu dosyayı BOZAMAZ. Şekil eşleyen bir redaktör,
# şekil eşleyen fixture'ları da eşler — bu dosya bir kez o yüzden bozuldu.
# Ayrıca gerçek değer yazmaya gerek yok: kalıbı sınamak için ŞEKİL yeterli.
_A, _B = 88, 99          # uydurma sayılar
_Y1, _Y2 = 1990, 1991    # uydurma yıllar


def _leak_shapes() -> list[str]:
    """Repoda GERÇEKTEN bulunmuş sızıntı şekilleri — sayılar uydurma."""
    return [
        f"- **Doğrulama (canlı):** {_Y1}–{_Y2} → {_A} rapor, {_B} test",   # data-models
        f"**Canlı: {_A} ziyaret.**",                                        # data-models
        f"**Canlı: {_A} kayıt.**",                                          # data-models
        f"tüm alanlar {_A}/{_A} dolu",                                      # data-models
        f"sunucu durumu {_A} normal / {_B} ref_disi",                       # data-models KLİNİK
        f"value/unit/reference {_A}/{_A}; durum temiz",                     # data-models
        f"**Canlı kayıt sayıları (bu hesap):** tahlil {_A} rapor",          # STATUS.md etiketi
        f"tanı {_A} · reçete {_B} · ziyaret {_A} ·",                        # STATUS.md envanteri
        f"token yükü iç içe ({_A} test ≈ 14.7k token)",                     # STATUS.md
        f"varsayılan aralıkta {_A} sonuç döndürebiliyor",                   # _common.py
        f"Kartlar render edilir ({_Y1}–{_Y2} için {_A} kayıt gözlendi)",    # endpoints.md
        f"canlı veri {_A} rapor / {_B} test",                               # labs.py
        f"**Canlı: {_A} KB geçerli PDF.**",                                 # data-models
    ]


def test_pattern_catches_every_real_leak_shape():
    """Kalıp, repoda GERÇEKTEN bulunmuş her şekli yakalamalı."""
    missed = [s for s in _leak_shapes() if not _CARDINALITY.search(s)]
    assert not missed, f"kalıp bu şekilleri kaçırdı: {missed}"


def test_pattern_accepts_anonymised_form():
    """Anonim hâller eşleşmemeli — aksi halde test kullanılamaz olurdu."""
    ok = [
        "**Canlı: onlarca kayıt.**",
        "**Canlı: birkaç kayıt.**",
        "- **Doğrulama (canlı):** çok sayıda rapor/test",
        "- **Doğrulama (canlı):** birkaç randevu, tüm alan dolu",
        "onlarca reçete; tüm alanlar istisnasız dolu.",
        "Kartlar sayfada render edilir (canlıda kayıt gözlendi)",
        "**Canlı doğrulama:** tüm alanlar gerçek bir hesapta çalıştırıldı",
        "bir rapor çok sayıda test taşır",
        "## Faz 2 — Klinik çekirdek (canlı keşifle doğrulandı 2026-07-13) ✅",  # geliştirme tarihi
    ]
    bad = [s for s in ok if _CARDINALITY.search(s)]
    assert not bad, f"yanlış pozitif: {bad}"


def test_scanner_year_range_is_not_flagged():
    """`year_range: 2021-2026` tarayıcının SORGU PENCERESİ, kullanıcının verisi değil.

    `discover.py:211` → `this_year - 5`. Sıfır kaydı olan kullanıcı da aynısını görür.
    İşaretlemek testi gürültüye boğar ve asıl sinyali kaybettirirdi.
    """
    meta = f"**Özet:** pages_scanned: 14 · year_range: {_Y1}-{_Y2} · mode: replay"
    assert not _CARDINALITY.search(meta)
    # Ama VERİ bağlamındaki aynı şekilli aralık yakalanmalı:
    assert _CARDINALITY.search(f"- **Doğrulama (canlı):** {_Y1}–{_Y2} → {_A} rapor")
