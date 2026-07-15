"""Hastane ziyareti parser'ı için birim testleri (sentetik fixture, PHI yok)."""

from pathlib import Path

from enabiz_mcp._text import tr_contains
from enabiz_mcp.parsers import parse_hospital_visits

FX = Path(__file__).parent / "fixtures"


def test_counts_and_fields():
    html = (FX / "ziyaret_sample.html").read_text(encoding="utf-8")
    items = parse_hospital_visits(html)
    assert len(items) == 2
    v = items[0]
    assert v.date == "03.03.2024"
    assert v.hospital == "T.C. SAĞLIK BAKANLIĞI TEST ŞEHİR HASTANESİ"
    assert v.clinic == "İÇ HASTALIKLARI"
    assert v.doctor == "DR TEST A"
    assert v.tracking_no == "TKP001"  # "Hastane Takip No:" etiketi sıyrıldı
    assert items[1].tracking_no == "TKP002"
    # Detay referansı GetZiyaretDetay onclick'inden çıkarıldı (&amp; çözülür)
    assert v.detail_ref is not None and v.detail_ref.startswith("data=DREF001")
    assert "hastane=H1" in v.detail_ref


def test_turkish_query_filter_matches_uppercase_data():
    """Tool'un filtre mantığı Türkçe TÜMÜ-BÜYÜK veriyi bulmalı.

    Portal verisi büyük harftir; düz `.lower()` ile bu sorgular 0 döndürüyordu
    (`'İ'.lower()` == 'i' + U+0307, `'I'.lower()` == ASCII 'i'). Regresyon olursa
    kullanıcı sessizce "kayıt yok" cevabı alır.
    """
    html = (FX / "ziyaret_sample.html").read_text(encoding="utf-8")
    items = parse_hospital_visits(html)

    def tool_filter(query):  # tools/hospital_visits.py ile aynı ifade
        return [
            v for v in items
            if tr_contains(query, v.hospital) or tr_contains(query, v.clinic)
        ]

    assert len(tool_filter("şehir")) == 1  # İ'den SONRA karakter var → eski hata
    assert len(tool_filter("ŞEHİR")) == 1
    assert len(tool_filter("iç hastalıkları")) == 1
    assert len(tool_filter("aile hekimliği")) == 1
    assert len(tool_filter("hastanesi")) == 1  # terminal İ — eskiden de çalışıyordu
    assert len(tool_filter("yok böyle bir şey")) == 0

    # Eski davranışın gerçekten kırık olduğunu sabitle: bu düzeltmenin gerekçesi.
    naive = [v for v in items if "şehir" in (v.hospital or "").lower()]
    assert naive == []
