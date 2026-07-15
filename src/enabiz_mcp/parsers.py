"""E-Nabız HTML yanıt ayrıştırıcıları.

`/Tahlil/Index` bir HTML accordion partial'ı döndürür (bkz. docs/findings/data-models.md):
  .accordion-item  = bir tarih/ziyaret (hastane) grubu
    .zCardDateGun/Ay/Yil = tarih parçaları
    .hastaneAdi          = kurum adı
    .rowContainer        = tekil test sonucu (6 kolon):
       [0] islemAdiContainer  → test adı
       [1] sonuç · [2] birim · [3] referans
       [4] karsilastirmaContainer (trend butonu)
       [5] durumNormal | durumRefdisi (referans durumu)
"""

from __future__ import annotations

import math
import re

from bs4 import BeautifulSoup, NavigableString
from pydantic import BaseModel, Field


class LabResult(BaseModel):
    """Tekil laboratuvar test sonucu."""

    test: str = Field(description="Test/tetkik adı")
    value: str | None = Field(default=None, description="Sonuç değeri")
    unit: str | None = Field(default=None, description="Birim")
    reference: str | None = Field(default=None, description="Referans aralığı")
    status: str = Field(
        description="SUNUCUNUN referans durumu sınıflandırması: normal | ref_disi | unknown "
        "(E-Nabız tek-üst-sınırlı '-Y' referansları değerlendirmeyip normal'e düşürebilir)"
    )
    out_of_range: bool | None = Field(
        default=None,
        description="Değerin referans dışı olup olmadığının BAĞIMSIZ hesabı; çözülemezse None. "
        "Sunucunun kaçırdığı tek-sınırlı referansları yakalar — kritik güvenlik alanı.",
    )
    trend_code: str | None = Field(
        default=None, description="Trend için IslemTipi kodu (enabiz_get_lab_trend'e geçilir)"
    )


class LabReport(BaseModel):
    """Bir tarih/ziyaretteki tahlil grubu."""

    date: str = Field(description="Tarih (gün.ay.yıl)")
    hospital: str | None = Field(default=None, description="Kurum/hastane adı")
    results: list[LabResult] = Field(default_factory=list)
    card_tarih: str | None = Field(
        default=None, description="PDF için tarih (enabiz_download_document kind='lab')"
    )
    kurum_kodu: str | None = Field(
        default=None, description="PDF için kurum kodu (enabiz_download_document kind='lab')"
    )


def _text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _col_value(cc) -> str:
    """Tahlil `.columnContainer`'ından değeri döndürür — baştaki etiket `<span>`'ini
    (ör. "Sonuç :", "Referans Değeri :") hariç tutar.

    Gerçek yapı: `<div class="columnContainer"><span>Sonuç :</span>8,54</div>`.
    Değer, span'in dışındaki doğrudan metin düğümüdür.
    """
    if cc is None:
        return ""
    direct = " ".join(
        str(s).strip() for s in cc.contents if isinstance(s, NavigableString) and str(s).strip()
    )
    if direct:
        return direct
    # Değer bir alt-etikette ise: etiket span metnini tam metinden düş.
    full = cc.get_text(" ", strip=True)
    label = cc.find("span")
    lbl = label.get_text(" ", strip=True) if label else ""
    if lbl and full.startswith(lbl):
        return full[len(lbl):].strip()
    return full


def _status(rc) -> str:
    classes: set[str] = set()
    for cc in rc.select(".columnContainer"):
        classes.update(cc.get("class") or [])
    if "durumRefdisi" in classes:
        return "ref_disi"
    if "durumNormal" in classes:
        return "normal"
    return "unknown"


# --------------------------------------------------------------------------- #
# Reçeteler — endpoint: POST /Recete/Index {baslangicYil, bitisYil}
# → HTML tablo #tbl-recetelerim (kolonlar: Tarih, Reçete No, Reçete Türü, Hekim, ...)
# Detay: ReceteDetayGoster(sysTakipNo, receteNo, ...) → /Recete/GetReceteDetay
# --------------------------------------------------------------------------- #
_RECETE_DETAY_RE = re.compile(r"ReceteDetayGoster\((.*?)\)")


class Prescription(BaseModel):
    """Bir reçete (ilaç detayı ayrı: get_prescription_detail)."""

    date: str = Field(description="Reçete tarihi")
    prescription_no: str = Field(description="Reçete numarası")
    type: str | None = Field(default=None, description="Reçete türü")
    doctor: str | None = Field(default=None, description="Reçeteyi yazan hekim")
    sys_takip_no: str | None = Field(default=None, description="Detay çağrısı için SYS takip no")


def _onclick_recete_args(tr) -> list[str]:
    """Satırdaki ReceteDetayGoster(...) argümanlarını çıkarır (sysTakipNo, receteNo, ...)."""
    for a in tr.find_all("a"):
        m = _RECETE_DETAY_RE.search(a.get("onclick", "") or "")
        if m:
            return [p.strip().strip("'\"") for p in m.group(1).split(",")]
    return []


def parse_prescriptions(html: str) -> list[Prescription]:
    """`/Recete/Index` HTML tablosunu yapılandırılmış reçetelere dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tbl-recetelerim")
    out: list[Prescription] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        no = _text(tds[1])
        if not no and not _text(tds[0]):
            continue
        args = _onclick_recete_args(tr)
        out.append(
            Prescription(
                date=_text(tds[0]),
                prescription_no=no or (args[1] if len(args) > 1 else ""),
                type=_text(tds[2]) or None,
                doctor=_text(tds[3]) or None,
                sys_takip_no=args[0] if args else None,
            )
        )
    return out


class PrescriptionDrug(BaseModel):
    """Reçetedeki bir ilaç (yazılan veya satılan)."""

    category: str = Field(description="prescribed (yazılan) | dispensed (satılan)")
    barcode: str | None = Field(default=None, description="İlaç barkodu")
    name: str | None = Field(default=None, description="İlaç adı")
    description: str | None = Field(default=None, description="Açıklama")
    dose: str | None = Field(default=None, description="Doz")
    period: str | None = Field(default=None, description="Periyot")
    usage: str | None = Field(default=None, description="Kullanım şekli")
    usage_count: str | None = Field(default=None, description="Kullanım sayısı")
    box_count: str | None = Field(default=None, description="Kutu adedi")


def _cell(tds: list[str], i: int) -> str | None:
    return (tds[i] or None) if i < len(tds) else None


def _rows(table):
    return table.select("tbody tr") or [tr for tr in table.find_all("tr") if not tr.find("th")]


def parse_prescription_detail(html: str) -> list[dict]:
    """`/Recete/GetReceteDetay` yanıtındaki yazılan+satılan ilaçları düz listeye çevirir."""
    soup = BeautifulSoup(html, "html.parser")
    drugs: list[dict] = []
    for table in soup.find_all("table"):
        tid = table.get("id") or ""
        if "Yazan" in tid:
            category = "prescribed"
        elif "Satilan" in tid:
            category = "dispensed"
        else:
            continue
        for tr in _rows(table):
            tds = [_text(td) for td in tr.find_all("td")]
            if not any(tds):
                continue
            if category == "prescribed":
                drug = PrescriptionDrug(
                    category=category,
                    barcode=_cell(tds, 0),
                    name=_cell(tds, 1),
                    description=_cell(tds, 2),
                    dose=_cell(tds, 3),
                    period=_cell(tds, 4),
                    usage=_cell(tds, 5),
                    usage_count=_cell(tds, 6),
                    box_count=_cell(tds, 7),
                )
            else:
                drug = PrescriptionDrug(
                    category=category,
                    barcode=_cell(tds, 0),
                    name=_cell(tds, 1),
                    box_count=_cell(tds, 2),
                )
            drugs.append(drug.model_dump())
    return drugs


# --------------------------------------------------------------------------- #
# Radyoloji — /Home/RadyolojikGoruntulerim sayfa-içi `.radyolojiCardListe` kartları
# (tablo/accordion değil). Rapor: POST /RadyolojikGoruntu/GetRaporByOrder {orderId}
# → HTML rapor (orderId = kart onclick'indeki şifreli token).
# --------------------------------------------------------------------------- #
_SHOW_REPORT_RE = re.compile(r"showHtmlReport\('([^']+)'\)")
_IMAGE_LINK_RE = re.compile(r"openImageLink\('([^']+)'\)")


class RadiologyStudy(BaseModel):
    """Bir radyolojik tetkik/görüntü kaydı."""

    date: str = Field(description="Tetkik tarihi")
    hospital: str | None = Field(default=None, description="Kurum/hastane adı")
    description: str | None = Field(default=None, description="Tetkik açıklaması/türü")
    order_id: str | None = Field(
        default=None, description="Rapor çağrısı için token (enabiz_get_radiology_report / _pdf)"
    )
    accession_number: str | None = Field(
        default=None, description="Görüntü (DICOM) linki için (enabiz_get_radiology_image_link)"
    )


def parse_radiology_studies(html: str) -> list[RadiologyStudy]:
    """`/Home/RadyolojikGoruntulerim` sayfa kartlarını radyoloji kayıtlarına çevirir."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[RadiologyStudy] = []
    for card in soup.select(".radyolojiCardListe"):
        date_raw = _text(card.select_one(".Rtarih"))
        order_id = None
        btn = card.find(lambda t: t.has_attr("onclick") and "showHtmlReport" in t["onclick"])
        if btn:
            m = _SHOW_REPORT_RE.search(btn["onclick"])
            if m:
                order_id = m.group(1)
        accession = None
        ibtn = card.find(lambda t: t.has_attr("onclick") and "openImageLink" in t["onclick"])
        if ibtn:
            im = _IMAGE_LINK_RE.search(ibtn["onclick"])
            if im:
                accession = im.group(1)
        out.append(
            RadiologyStudy(
                date=date_raw.split()[0] if date_raw else "",
                hospital=_text(card.select_one(".RhastaneAdi")) or None,
                description=_text(card.select_one(".Raciklama")) or None,
                order_id=order_id,
                accession_number=accession,
            )
        )
    return out


def html_to_text(html: str) -> str:
    """HTML'i okunabilir düz metne indirger (script/stil atılır).

    Yapısı bilinmeyen/serbest-metin detay yanıtları için (radyoloji raporu,
    hastalık detayı vb.) yapılandırılmış parse yerine kullanılır.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)




# --------------------------------------------------------------------------- #
# Randevular — /Home/Randevularim sayfa-içi tablo #tblRandevuListesi
# (sunucu-render; ayrı liste endpoint'i yok). Yalnızca okunur — aksiyon YOK.
# --------------------------------------------------------------------------- #
class Appointment(BaseModel):
    """Bir MHRS randevusu (salt-okunur kayıt)."""

    date_time: str = Field(description="Randevu tarih/saati")
    institution: str | None = Field(default=None, description="Kurum")
    clinic: str | None = Field(default=None, description="Klinik")
    location: str | None = Field(default=None, description="Muayene yeri")
    doctor: str | None = Field(default=None, description="Hekim")
    status: str | None = Field(default=None, description="Durum")
    type: str | None = Field(default=None, description="Randevu türü")


def parse_appointments(html: str) -> list[Appointment]:
    """`/Home/Randevularim` tablosunu yapılandırılmış randevulara dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tblRandevuListesi")
    out: list[Appointment] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < 5 or not any(tds[:5]):
            continue
        out.append(
            Appointment(
                date_time=_cell(tds, 0) or "",
                institution=_cell(tds, 1),
                clinic=_cell(tds, 2),
                location=_cell(tds, 3),
                doctor=_cell(tds, 4),
                status=_cell(tds, 5),
                type=_cell(tds, 6),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# İlaçlar — endpoint: POST /Ilac/Index {baslangicYil, bitisYil}
# → HTML tablo #tblIlaclarim (13 kolon; self-contained, reçete bazlı düz liste)
# --------------------------------------------------------------------------- #
class Medication(BaseModel):
    """Kullanılan bir ilaç (reçete bağlamıyla, düz kayıt)."""

    prescription_date: str = Field(description="Reçete tarihi")
    barcode: str | None = Field(default=None, description="İlaç barkodu")
    prescription_no: str | None = Field(default=None, description="Reçete no")
    name: str | None = Field(default=None, description="İlaç adı")
    dose: str | None = Field(default=None, description="Doz")
    period: str | None = Field(default=None, description="Periyot")
    usage: str | None = Field(default=None, description="Kullanım şekli")
    usage_count: str | None = Field(default=None, description="Kullanım sayısı")
    box_count: str | None = Field(default=None, description="Kutu adedi")
    hospital: str | None = Field(default=None, description="Hastane adı")
    clinic: str | None = Field(default=None, description="Klinik adı")


def parse_medications(html: str) -> list[Medication]:
    """`/Ilac/Index` HTML tablosunu yapılandırılmış ilaç listesine dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tblIlaclarim")
    out: list[Medication] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < 4 or not any(tds[:4]):
            continue
        out.append(
            Medication(
                prescription_date=_cell(tds, 0) or "",
                barcode=_cell(tds, 1),
                prescription_no=_cell(tds, 2),
                name=_cell(tds, 3),
                dose=_cell(tds, 4),
                period=_cell(tds, 5),
                usage=_cell(tds, 6),
                usage_count=_cell(tds, 7),
                box_count=_cell(tds, 8),
                hospital=_cell(tds, 9),
                clinic=_cell(tds, 10),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Sağlık raporları — endpoint: POST /Rapor/Index {startYear, endYear}
# → HTML tablo #tblRaporlarim (self-contained; detay çağrısı gerekmez)
# --------------------------------------------------------------------------- #
class Report(BaseModel):
    """Bir sağlık raporu (self-contained satır)."""

    date: str = Field(description="Rapor tarihi")
    report_no: str | None = Field(default=None, description="Rapor no")
    tracking_no: str | None = Field(default=None, description="Rapor takip numarası")
    type: str | None = Field(default=None, description="Rapor türü")
    start_date: str | None = Field(default=None, description="Geçerlilik başlangıç tarihi")
    end_date: str | None = Field(default=None, description="Geçerlilik bitiş tarihi")
    diagnosis: str | None = Field(default=None, description="Tanı")


def parse_reports(html: str) -> list[Report]:
    """`/Rapor/Index` HTML tablosunu yapılandırılmış raporlara dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tblRaporlarim")
    out: list[Report] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < 7 or not any(tds[:7]):
            continue
        out.append(
            Report(
                date=_cell(tds, 0) or "",
                report_no=_cell(tds, 1),
                tracking_no=_cell(tds, 2),
                type=_cell(tds, 3),
                start_date=_cell(tds, 4),
                end_date=_cell(tds, 5),
                diagnosis=_cell(tds, 6),
            )
        )
    return out


# Tahlil trend — .karsilastirmaBtn onclick="GrafikGoster('<IslemTipi>')" → trend_code.
# GET /Tahlil/TahlillerRapor {IslemTipi} → tablo #tbltahlilTablo (canlı doğrulandı).
_GRAFIK_RE = re.compile(r"GrafikGoster\('([^']+)'\)")
# Lab PDF — .pdfBtnSmall onclick="TahlillerPdfIndir('<dil>','<cardTarih>','<kurumKodu>')".
# (dil atlanır; tarih + kurum kodu yakalanır → enabiz_download_document) — canlı doğrulandı.
_TAHLIL_PDF_RE = re.compile(r"TahlillerPdfIndir\(\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*'([^']*)'")


def _num(s: str | None) -> float | None:
    """Sayısal metni float'a çevirir (Türkçe virgül-ondalık dahil); değilse None.

    `float()` "nan"/"inf" dizelerini de kabul eder; bunlar elenir. Aksi hâlde
    `_compute_out_of_range("nan", ...)` False ("aralıkta") dönerdi — nan
    karşılaştırmalarının tamamı False olduğu için — yani güvenlik-kritik alanda
    yanlış-negatif.
    """
    if not s:
        return None
    try:
        v = float(s.strip().replace(",", "."))
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _compute_out_of_range(value: str | None, reference: str | None) -> bool | None:
    """Sonucu referans aralığıyla kıyaslayıp aralık dışı mı belirler (bağımsız kontrol).

    `status` sunucunun sınıflandırmasıdır; bu ise BİZİM hesabımızdır — özellikle sunucunun
    değerlendirmediği tek-sınırlı referansları (`-Y`, `Y-`, `<Y`, `>X`) yakalar. Güvenli
    tarafta kalır: değer/referans sayısal olarak çözülemiyorsa **None** döner (yanlış-pozitif yok).
    """
    v = _num(value)
    if v is None:
        return None
    ref = (reference or "").strip()
    if not ref or ref == "-":
        return None
    if ref.startswith("<"):
        y = _num(ref[1:])
        return (v > y) if y is not None else None
    if ref.startswith(">"):
        x = _num(ref[1:])
        return (v < x) if x is not None else None
    if ref.startswith("-"):  # tek üst sınır: "-2,7" → v > 2,7 aralık dışı
        y = _num(ref[1:])
        return (v > y) if y is not None else None
    if ref.endswith("-"):  # tek alt sınır: "5-" → v < 5 aralık dışı
        x = _num(ref[:-1])
        return (v < x) if x is not None else None
    if "-" in ref:  # iki uçlu: "9,3-12,1"
        lo, hi = ref.split("-", 1)
        x, y = _num(lo), _num(hi)
        if x is not None and y is not None:
            return v < x or v > y
    return None


class LabTrendPoint(BaseModel):
    """Bir testin zaman içindeki tek ölçümü (trend noktası)."""

    date: str = Field(description="Tarih")
    value: str | None = Field(default=None, description="Sonuç")
    unit: str | None = Field(default=None, description="Sonuç birimi")
    reference: str | None = Field(default=None, description="Referans değeri")


def parse_lab_trend(html: str) -> list[LabTrendPoint]:
    """`/Tahlil/TahlillerRapor` yanıtındaki `#tbltahlilTablo` trend tablosunu ayrıştırır."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tbltahlilTablo")
    out: list[LabTrendPoint] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if not tds or not any(tds[:1]):
            continue
        out.append(
            LabTrendPoint(
                date=_cell(tds, 0) or "",
                value=_cell(tds, 1),
                unit=_cell(tds, 2),
                reference=_cell(tds, 3),
            )
        )
    return out


def parse_lab_reports(html: str) -> list[LabReport]:
    """`/Tahlil/Index` HTML partial'ını yapılandırılmış tahlil raporlarına dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    reports: list[LabReport] = []

    for item in soup.select(".accordion-item"):
        gun = _text(item.select_one(".zCardDateGun"))
        ay = _text(item.select_one(".zCardDateAy"))
        yil = _text(item.select_one(".zCardDateYil"))
        date = ".".join(p for p in (gun, ay, yil) if p)
        hospital = _text(item.select_one(".hastaneAdi")) or None

        results: list[LabResult] = []
        for rc in item.select(".rowContainer"):
            cols = rc.select(".columnContainer")
            if not cols:
                continue
            name = _col_value(cols[0])
            if not name:
                continue
            tcode = None
            btn = rc.select_one(".karsilastirmaContainer a, a.karsilastirmaBtn")
            if btn and btn.get("onclick"):
                mm = _GRAFIK_RE.search(btn["onclick"])
                if mm:
                    tcode = mm.group(1)
            value = (_col_value(cols[1]) or None) if len(cols) > 1 else None
            reference = (_col_value(cols[3]) or None) if len(cols) > 3 else None
            results.append(
                LabResult(
                    test=name,
                    value=value,
                    unit=(_col_value(cols[2]) or None) if len(cols) > 2 else None,
                    reference=reference,
                    status=_status(rc),
                    out_of_range=_compute_out_of_range(value, reference),
                    trend_code=tcode,
                )
            )
        if results:
            card_tarih = kurum_kodu = None
            pbtn = item.find(
                lambda t: t.has_attr("onclick") and "TahlillerPdfIndir" in t["onclick"]
            )
            if pbtn:
                pm = _TAHLIL_PDF_RE.search(pbtn["onclick"])
                if pm:
                    card_tarih, kurum_kodu = pm.group(1), pm.group(2)
            reports.append(
                LabReport(
                    date=date,
                    hospital=hospital,
                    results=results,
                    card_tarih=card_tarih,
                    kurum_kodu=kurum_kodu,
                )
            )

    return reports


# =========================================================================== #
# FAZ 2 — Klinik çekirdek alanları (canlı keşifle doğrulandı 2026-07-13)
# Çoğu alan SUNUCU-RENDER: veri doğrudan /Home/<Ad> sayfasındaki #tbl<Ad>
# tablosunda (ayrı AJAX yok). Epikriz/Patoloji ayrıca POST /<Alan>/Index sunar.
# =========================================================================== #
def _row_token(tr, pattern: re.Pattern) -> str | None:
    """Satırdaki bir onclick içinden verilen regex ile ilk token'ı çıkarır."""
    for el in tr.find_all(lambda t: t.has_attr("onclick")):
        m = pattern.search(el.get("onclick", "") or "")
        if m:
            return m.group(1)
    return None


# --------------------------------------------------------------------------- #
# Alerjiler — GET /Home/Alerjilerim, 3 tablo (ilaç / tanı-bazlı / deri testi)
# Her tablo 6 kolon: Tarih · Alerji Türü · İlaç Adı · Belirtileri · (aksiyon) · (aksiyon)
# --------------------------------------------------------------------------- #
_ALLERGY_TABLES = (
    ("tblAlerjilerim", "ilac"),
    ("tblAlerjilerTanilarim", "tani"),
    ("tblAlerjilerDeri", "deri"),
)


class Allergy(BaseModel):
    """Bir alerji kaydı (3 kategoriden biri)."""

    date: str = Field(description="Kayıt tarihi")
    category: str = Field(description="Kategori: ilac | tani | deri")
    allergy_type: str | None = Field(default=None, description="Alerji türü")
    drug_name: str | None = Field(default=None, description="İlaç adı")
    symptoms: str | None = Field(default=None, description="Belirtileri")


def parse_allergies(html: str) -> list[Allergy]:
    """`/Home/Alerjilerim` sayfasındaki 3 alerji tablosunu tek listeye çevirir."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[Allergy] = []
    for table_id, category in _ALLERGY_TABLES:
        table = soup.select_one(f"#{table_id}")
        if table is None:
            continue
        for tr in _rows(table):
            tds = [_text(td) for td in tr.find_all("td")]
            if len(tds) < 4 or not any(tds[:4]):
                continue
            out.append(
                Allergy(
                    date=_cell(tds, 0) or "",
                    category=category,
                    allergy_type=_cell(tds, 1),
                    drug_name=_cell(tds, 2),
                    symptoms=_cell(tds, 3),
                )
            )
    return out


# --------------------------------------------------------------------------- #
# Tanılar/hastalıklar — GET /Home/Hastaliklarim, tablo #tblHastaliklarim
# Kolonlar: Tarih · Tanı · Klinik · Hekim · (Detay). Detay: HastalikDetayGoster(
#   tarih, tani, ..., SysTakipNo) → GET /hastalik/GetHastalikDetay (HTML).
# Not: `tani` kolonu virgüllü ICD kodları içerebilir → SysTakipNo son argümandır,
# bu yüzden regex SON tırnaklı argümanı yakalar.
# --------------------------------------------------------------------------- #
_HASTALIK_TOKEN_RE = re.compile(r"HastalikDetayGoster\(.*,\s*['\"]([^'\"]*)['\"]\s*\)", re.S)


class Diagnosis(BaseModel):
    """Bir tanı/hastalık kaydı."""

    date: str = Field(description="Tanı tarihi")
    diagnosis: str | None = Field(default=None, description="Tanı (ICD kodu + ad)")
    clinic: str | None = Field(default=None, description="Klinik")
    doctor: str | None = Field(default=None, description="Hekim")
    sys_takip_no: str | None = Field(
        default=None, description="Detay için token (enabiz_get_diagnosis_detail)"
    )


def parse_diagnoses(html: str) -> list[Diagnosis]:
    """`/Home/Hastaliklarim` tablosunu yapılandırılmış tanılara dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tblHastaliklarim")
    out: list[Diagnosis] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < 4 or not any(tds[:4]):
            continue
        out.append(
            Diagnosis(
                date=_cell(tds, 0) or "",
                diagnosis=_cell(tds, 1),
                clinic=_cell(tds, 2),
                doctor=_cell(tds, 3),
                sys_takip_no=_row_token(tr, _HASTALIK_TOKEN_RE),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Kronik hastalık takibi — GET /Home/HastalikTakip, tablo #tblHastalikTakip
# Kolonlar: Takip Tipi · Kronik Hastalık · Takip Tarihi · Planlanan Takip Tarihi
#   · Gerçekleşti mi? · (aksiyon). Detay: HastalikTakipDetayGoster(sysTakipNo).
# --------------------------------------------------------------------------- #
_TAKIP_TOKEN_RE = re.compile(r"HastalikTakipDetayGoster\(['\"]([^'\"]*)['\"]\)")


class ChronicFollowup(BaseModel):
    """Kronik hastalık takip kaydı."""

    followup_type: str = Field(description="Takip tipi")
    chronic_disease: str | None = Field(default=None, description="Kronik hastalık")
    followup_date: str | None = Field(default=None, description="Takip tarihi")
    planned_date: str | None = Field(default=None, description="Planlanan takip tarihi")
    realized: str | None = Field(default=None, description="Gerçekleşti mi?")
    sys_takip_no: str | None = Field(default=None, description="Detay için token")


def parse_chronic_followups(html: str) -> list[ChronicFollowup]:
    """`/Home/HastalikTakip` tablosunu kronik takip kayıtlarına dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tblHastalikTakip")
    out: list[ChronicFollowup] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < 5 or not any(tds[:5]):
            continue
        out.append(
            ChronicFollowup(
                followup_type=_cell(tds, 0) or "",
                chronic_disease=_cell(tds, 1),
                followup_date=_cell(tds, 2),
                planned_date=_cell(tds, 3),
                realized=_cell(tds, 4),
                sys_takip_no=_row_token(tr, _TAKIP_TOKEN_RE),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Aşılar — GET /Home/AsiTakvimi, tablo #tblAsilar (detay yok, hepsi düz metin)
# Kolonlar: İşlem Zamanı · Yapılan Aşılar · Aşı Dozu · Aşı Yapılma Yeri
# --------------------------------------------------------------------------- #
class Vaccination(BaseModel):
    """Bir aşı kaydı."""

    date: str = Field(description="İşlem zamanı")
    vaccine: str | None = Field(default=None, description="Yapılan aşı")
    dose: str | None = Field(default=None, description="Aşı dozu")
    location: str | None = Field(default=None, description="Aşı yapılma yeri")


def parse_vaccinations(html: str) -> list[Vaccination]:
    """`/Home/AsiTakvimi` tablosunu yapılandırılmış aşı kayıtlarına dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tblAsilar")
    out: list[Vaccination] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < 4 or not any(tds[:4]):
            continue
        out.append(
            Vaccination(
                date=_cell(tds, 0) or "",
                vaccine=_cell(tds, 1),
                dose=_cell(tds, 2),
                location=_cell(tds, 3),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Epikrizler & Patolojiler — POST /Epikriz/Index {baslangicYil,bitisYil} ve
# POST /Patoloji/Index {baslangicYili,bitisYili} (⚠ param adları FARKLI).
# Tablolar #tblEpikriz / #tblPatoloji, aynı 6 kolon:
#   Tarih · Referans No · Hastane · Klinik · Hekim · (PDF: PDFGetir(sysNo, referansNo))
# Detay = PDF (Faz 4). Liste model'i sys_no'yu Faz 4 PDF tool'u için taşır.
# --------------------------------------------------------------------------- #
_PDF_GETIR_RE = re.compile(r"PDFGetir\(['\"]([^'\"]*)['\"]")


class DischargeSummary(BaseModel):
    """Bir epikriz (taburcu özeti) kaydı."""

    date: str = Field(description="Tarih")
    reference_no: str | None = Field(default=None, description="Referans no")
    hospital: str | None = Field(default=None, description="Hastane")
    clinic: str | None = Field(default=None, description="Klinik")
    doctor: str | None = Field(default=None, description="Hekim")
    sys_no: str | None = Field(default=None, description="PDF için sys no (Faz 4)")


class Pathology(BaseModel):
    """Bir patoloji kaydı."""

    date: str = Field(description="Tarih")
    reference_no: str | None = Field(default=None, description="Referans no")
    hospital: str | None = Field(default=None, description="Hastane")
    clinic: str | None = Field(default=None, description="Klinik")
    doctor: str | None = Field(default=None, description="Hekim")
    sys_no: str | None = Field(default=None, description="PDF için sys no (Faz 4)")


def _parse_referans_table(html: str, table_id: str, cls):
    """Epikriz/Patoloji ortak 6-kolon tablo ayrıştırıcısı (Referans No + PDF token)."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one(f"#{table_id}")
    out: list = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < 5 or not any(tds[:5]):
            continue
        out.append(
            cls(
                date=_cell(tds, 0) or "",
                reference_no=_cell(tds, 1),
                hospital=_cell(tds, 2),
                clinic=_cell(tds, 3),
                doctor=_cell(tds, 4),
                sys_no=_row_token(tr, _PDF_GETIR_RE),
            )
        )
    return out


def parse_discharge_summaries(html: str) -> list[DischargeSummary]:
    """`/Epikriz/Index` tablosunu yapılandırılmış epikrizlere dönüştürür."""
    return _parse_referans_table(html, "tblEpikriz", DischargeSummary)


def parse_pathology(html: str) -> list[Pathology]:
    """`/Patoloji/Index` tablosunu yapılandırılmış patoloji kayıtlarına dönüştürür."""
    return _parse_referans_table(html, "tblPatoloji", Pathology)


# =========================================================================== #
# FAZ 3 — Ziyaretler + Profil (canlı keşifle doğrulandı 2026-07-13)
# =========================================================================== #

# --------------------------------------------------------------------------- #
# Hastane ziyaretleri (muayeneler) — POST /Ziyaret/Index {baslangicYil,bitisYil}
# → kart ızgarası #ziyaretlerContainer > .ziyaretCardList (tablo/accordion DEĞİL).
# Alanlar: .zTarihS (gizli tam tarih) · .card-text (hastane) · .drBrans (klinik)
#   · .drAdi (hekim) · .hastaneTakipNo ("Hastane Takip No: <token>").
# Detay: kart "Detay Görüntüle" onclick'i GetZiyaretDetay?<qs> → enabiz_get_visit_detail.
# --------------------------------------------------------------------------- #
_VISIT_DETAIL_RE = re.compile(r"GetZiyaretDetay\?([^'\"]+)")


def _strip_label(text: str) -> str:
    """"Etiket: değer" biçiminden değeri döndürür ("Hastane Takip No: X" → "X")."""
    return text.split(":", 1)[1].strip() if ":" in text else text.strip()


class HospitalVisit(BaseModel):
    """Bir hastane ziyareti (muayene) özeti."""

    date: str = Field(description="Ziyaret tarihi")
    hospital: str | None = Field(default=None, description="Hastane")
    clinic: str | None = Field(default=None, description="Klinik/branş")
    doctor: str | None = Field(default=None, description="Hekim")
    tracking_no: str | None = Field(default=None, description="Hastane takip no")
    detail_ref: str | None = Field(
        default=None, description="Detay için opak referans (enabiz_get_visit_detail'e geçilir)"
    )


def parse_hospital_visits(html: str) -> list[HospitalVisit]:
    """`/Ziyaret/Index` kart ızgarasını yapılandırılmış ziyaretlere dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[HospitalVisit] = []
    for card in soup.select(".ziyaretCardList"):
        date = _text(card.select_one(".zTarihS"))
        if not date:  # gizli tam tarih yoksa parçalardan kur (gün ay yıl)
            parts = [
                _text(card.select_one(f".zCardDate{p}")) for p in ("Gun", "Ay", "Yil")
            ]
            date = " ".join(p for p in parts if p)
        takip = _text(card.select_one(".hastaneTakipNo"))
        out.append(
            HospitalVisit(
                date=date,
                hospital=_text(card.select_one(".card-text")) or None,
                clinic=_text(card.select_one(".drBrans")) or None,
                doctor=_text(card.select_one(".drAdi")) or None,
                tracking_no=_strip_label(takip) if takip else None,
                detail_ref=_row_token(card, _VISIT_DETAIL_RE),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Profil — GET /Home/ProfilBilgilerim (veri SAYFADA; en temiz kaynak inline
# `var orgData = {'Boy','Kilo','KanGrubu',...}` JS objesi). Kimlik kartı alanları
# `data-bs-original-title`/`title` ile etiketlenir. TCKN/iletişim çıktıya dahil DEĞİL.
# --------------------------------------------------------------------------- #
_BLOOD_TYPES = {
    "1": "A Rh+", "2": "B Rh+", "3": "AB Rh+", "4": "0 Rh+",
    "5": "0 Rh-", "6": "A Rh-", "7": "B Rh-", "8": "AB Rh-",
}
_ORGDATA_RE = re.compile(r"orgData\s*=\s*\{(.*?)\}", re.S)


class Profile(BaseModel):
    """Kullanıcı profil özeti (salt-okunur; TCKN/e-posta/telefon hariç)."""

    full_name: str | None = Field(default=None, description="Adı soyadı")
    birth_date: str | None = Field(default=None, description="Doğum tarihi")
    blood_type: str | None = Field(default=None, description="Kan grubu")
    height_cm: str | None = Field(default=None, description="Boy (cm)")
    weight_kg: str | None = Field(default=None, description="Kilo (kg)")
    family_physician: str | None = Field(default=None, description="Aile hekimi bilgileri")


def parse_profile(html: str) -> Profile:
    """`/Home/ProfilBilgilerim` sayfasını tek `Profile` nesnesine dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")

    m = _ORGDATA_RE.search(html)
    org = m.group(1) if m else ""

    def _org(key: str) -> str | None:
        mm = re.search(rf"['\"]{key}['\"]\s*:\s*['\"]([^'\"]*)['\"]", org)
        return (mm.group(1).strip() or None) if mm else None

    def _by_title(title: str) -> str | None:
        el = soup.find(attrs={"data-bs-original-title": title}) or soup.find(attrs={"title": title})
        return (_text(el) or None) if el else None

    blood_code = _org("KanGrubu")
    ta = soup.find("textarea")
    return Profile(
        full_name=_by_title("Adı Soyadı"),
        birth_date=_by_title("Doğum Tarihi"),
        blood_type=_BLOOD_TYPES.get(blood_code) if blood_code else None,
        height_cm=_org("Boy"),
        weight_kg=_org("Kilo"),
        family_physician=(_text(ta) or None) if ta else None,
    )


# =========================================================================== #
# FAZ 3b — Ziyaret detayı (canlı yakalamayla doğrulandı 2026-07-13)
# GET /Ziyaret/GetZiyaretDetay?<qs> → 4 tablo: tanı / ön tanı / ek tanı / işlemler.
# =========================================================================== #
class VisitDiagnosis(BaseModel):
    """Ziyaret detayındaki bir tanı satırı (tanı / ön tanı / ek tanı)."""

    date: str = Field(description="Tarih")
    diagnosis: str | None = Field(default=None, description="Tanı")
    doctor: str | None = Field(default=None, description="Hekim")
    clinic: str | None = Field(default=None, description="Klinik")


class VisitProcedure(BaseModel):
    """Ziyaret detayındaki bir işlem satırı."""

    procedure_time: str = Field(description="İşlem zamanı")
    appointment_time: str | None = Field(default=None, description="Randevu zamanı")
    count: str | None = Field(default=None, description="Adet")
    procedure_name: str | None = Field(default=None, description="İşlem adı")


def _parse_diag_table(soup, table_id: str) -> list[dict]:
    table = soup.select_one(f"#{table_id}")
    out: list[dict] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < 2 or not any(tds[:2]):
            continue
        out.append(
            VisitDiagnosis(
                date=_cell(tds, 0) or "",
                diagnosis=_cell(tds, 1),
                doctor=_cell(tds, 2),
                clinic=_cell(tds, 3),
            ).model_dump()
        )
    return out


def parse_visit_detail(html: str) -> dict:
    """`/Ziyaret/GetZiyaretDetay` yanıtını tanı/ön tanı/ek tanı/işlem listelerine ayrıştırır."""
    soup = BeautifulSoup(html, "html.parser")

    procedures: list[dict] = []
    ptable = soup.select_one("#tblZiyaretlerimIslemler")
    if ptable is not None:
        for tr in _rows(ptable):
            tds = [_text(td) for td in tr.find_all("td")]
            if len(tds) < 2 or not any(tds[:2]):
                continue
            procedures.append(
                VisitProcedure(
                    procedure_time=_cell(tds, 0) or "",
                    appointment_time=_cell(tds, 1),
                    count=_cell(tds, 2),
                    procedure_name=_cell(tds, 3),
                ).model_dump()
            )

    return {
        "diagnoses": _parse_diag_table(soup, "tblZiyaretlerimTani"),
        "preliminary_diagnoses": _parse_diag_table(soup, "tblZiyaretlerimOnTani"),
        "additional_diagnoses": _parse_diag_table(soup, "tblZiyaretlerimEkTani"),
        "procedures": procedures,
    }


# =========================================================================== #
# FAZ 4a — Optik/cihaz reçeteleri + dokümanlar (kolonlar recetelerim/dokuman
# sayfa thead'lerinden doğrulandı; satırlar POST/sunucu-render ile gelir)
# =========================================================================== #

# --------------------------------------------------------------------------- #
# Optik reçeteler — POST /Recete/GetOptikReceteler {baslangicYil,bitisYil}
# → #tbl-optikRecetelerim: Tarih · Reçete No · Reçete Türü · Hekim · (aksiyon)
# --------------------------------------------------------------------------- #
class OpticalPrescription(BaseModel):
    """Bir optik (gözlük/lens) reçetesi."""

    date: str = Field(description="Reçete tarihi")
    prescription_no: str | None = Field(default=None, description="Reçete no")
    type: str | None = Field(default=None, description="Reçete türü")
    doctor: str | None = Field(default=None, description="Hekim")


def parse_optical_prescriptions(html: str) -> list[OpticalPrescription]:
    """`/Recete/GetOptikReceteler` tablosunu optik reçetelere dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tbl-optikRecetelerim")
    out: list[OpticalPrescription] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < 4 or not any(tds[:4]):
            continue
        out.append(
            OpticalPrescription(
                date=_cell(tds, 0) or "",
                prescription_no=_cell(tds, 1),
                type=_cell(tds, 2),
                doctor=_cell(tds, 3),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Tıbbi cihaz reçeteleri — POST /Recete/GetTibbiCihazReceteler {baslangicYil,bitisYil}
# → #tbl-tibbiCihazRecetelerim: Tarih · Reçete No · Hekim · Tesis Bilgisi · (aksiyon)
# --------------------------------------------------------------------------- #
class DevicePrescription(BaseModel):
    """Bir tıbbi cihaz reçetesi."""

    date: str = Field(description="Reçete tarihi")
    prescription_no: str | None = Field(default=None, description="Reçete no")
    doctor: str | None = Field(default=None, description="Hekim")
    facility: str | None = Field(default=None, description="Tesis bilgisi")


def parse_device_prescriptions(html: str) -> list[DevicePrescription]:
    """`/Recete/GetTibbiCihazReceteler` tablosunu tıbbi cihaz reçetelerine dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tbl-tibbiCihazRecetelerim")
    out: list[DevicePrescription] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < 4 or not any(tds[:4]):
            continue
        out.append(
            DevicePrescription(
                date=_cell(tds, 0) or "",
                prescription_no=_cell(tds, 1),
                doctor=_cell(tds, 2),
                facility=_cell(tds, 3),
            )
        )
    return out


# =========================================================================== #
# FAZ 4b — İlaç kullanım geçmişi (canlı yakalamayla doğrulandı 2026-07-14)
# POST /Recete/GetIlacKullanimGecmisi {barcode} → tablo #tbIlacGecmis, 8 kolon.
# =========================================================================== #
class DrugUsage(BaseModel):
    """Bir ilacın tek kullanım kaydı (barkod bazlı geçmiş)."""

    date: str = Field(description="Tarih")
    barcode: str | None = Field(default=None, description="Barkod")
    name: str | None = Field(default=None, description="İlaç adı")
    description: str | None = Field(default=None, description="İlaç açıklaması")
    dose: str | None = Field(default=None, description="Kullanım dozu")
    usage_count: str | None = Field(default=None, description="Kullanım sayısı")
    period: str | None = Field(default=None, description="Kullanım periyodu")
    usage_form: str | None = Field(default=None, description="Kullanım şekli")


def parse_drug_usage_history(html: str) -> list[DrugUsage]:
    """`/Recete/GetIlacKullanimGecmisi` tablosunu ilaç kullanım kayıtlarına dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tbIlacGecmis")
    out: list[DrugUsage] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < 2 or not any(tds[:2]):
            continue
        out.append(
            DrugUsage(
                date=_cell(tds, 0) or "",
                barcode=_cell(tds, 1),
                name=_cell(tds, 2),
                description=_cell(tds, 3),
                dose=_cell(tds, 4),
                usage_count=_cell(tds, 5),
                period=_cell(tds, 6),
                usage_form=_cell(tds, 7),
            )
        )
    return out


# =========================================================================== #
# FAZ 5 — İdari alanlar (kolonlar sayfa thead'lerinden doğrulandı 2026-07-14;
# tümü sunucu-render GET-sayfa, bu hesapta 0 kayıt)
# =========================================================================== #

# Sigorta — GET /Home/Sigortalarim, #tblSigorta
# Kolonlar: Açıklama · Sigorta Kodu · Başlangıç-Bitiş Tarihleri · Bitiş Tarihi Ek Süre · Durum
class Insurance(BaseModel):
    """Bir sigorta kaydı."""

    description: str = Field(description="Açıklama")
    insurance_code: str | None = Field(default=None, description="Sigorta kodu")
    date_range: str | None = Field(default=None, description="Başlangıç-bitiş tarihleri")
    extra_period: str | None = Field(default=None, description="Bitiş tarihi ek süre")
    status: str | None = Field(default=None, description="Durum")


def parse_insurance(html: str) -> list[Insurance]:
    """`/Home/Sigortalarim` tablosunu yapılandırılmış sigorta kayıtlarına dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tblSigorta")
    out: list[Insurance] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < 2 or not any(tds[:2]):
            continue
        out.append(
            Insurance(
                description=_cell(tds, 0) or "",
                insurance_code=_cell(tds, 1),
                date_range=_cell(tds, 2),
                extra_period=_cell(tds, 3),
                status=_cell(tds, 4),
            )
        )
    return out


# Malzeme/cihaz — GET /Home/MalzemeveCihazlarim, 5 kategori tablosu (aynı yapı)
# Kolonlar: İşlem Tarihi · Marka · Raf Ömrü · Ürün Tanımı
_MATERIAL_TABLES = (
    ("tblMalzemeVeCihazlarimDiger", "diger"),
    ("tblMalzemeVeCihazlarimVucut", "vucut"),
    ("tblMalzemeVeCihazlarimIsitme", "isitme"),
    ("tblMalzemeVeCihazlarimGoz", "goz"),
    ("tblMalzemeVeCihazlarimOzelYapim", "ozel_yapim"),
)


class MaterialDevice(BaseModel):
    """Bir tıbbi malzeme/cihaz kaydı (kategorili)."""

    date: str = Field(description="İşlem tarihi")
    category: str = Field(description="Kategori: diger | vucut | isitme | goz | ozel_yapim")
    brand: str | None = Field(default=None, description="Marka")
    shelf_life: str | None = Field(default=None, description="Raf ömrü")
    product: str | None = Field(default=None, description="Ürün tanımı")


def parse_materials_devices(html: str) -> list[MaterialDevice]:
    """`/Home/MalzemeveCihazlarim` sayfasındaki 5 kategori tablosunu tek listeye çevirir."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[MaterialDevice] = []
    for table_id, category in _MATERIAL_TABLES:
        table = soup.select_one(f"#{table_id}")
        if table is None:
            continue
        for tr in _rows(table):
            tds = [_text(td) for td in tr.find_all("td")]
            if len(tds) < 2 or not any(tds[:2]):
                continue
            out.append(
                MaterialDevice(
                    date=_cell(tds, 0) or "",
                    category=category,
                    brand=_cell(tds, 1),
                    shelf_life=_cell(tds, 2),
                    product=_cell(tds, 3),
                )
            )
    return out


# Acil durum notları — GET /Home/AcilDurumNotlarim, #tblAcilDurum
# Kolonlar: Tarih · Konu · Açıklama
class EmergencyNote(BaseModel):
    """Bir acil durum notu."""

    date: str = Field(description="Tarih")
    subject: str | None = Field(default=None, description="Konu")
    description: str | None = Field(default=None, description="Açıklama")


def parse_emergency_notes(html: str) -> list[EmergencyNote]:
    """`/Home/AcilDurumNotlarim` tablosunu yapılandırılmış acil durum notlarına dönüştürür."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tblAcilDurum")
    out: list[EmergencyNote] = []
    if table is None:
        return out
    for tr in _rows(table):
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < 2 or not any(tds[:2]):
            continue
        out.append(
            EmergencyNote(
                date=_cell(tds, 0) or "",
                subject=_cell(tds, 1),
                description=_cell(tds, 2),
            )
        )
    return out
