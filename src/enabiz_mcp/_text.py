"""Türkçe metin yardımcıları.

Portal verisi TÜMÜ BÜYÜK HARF gelir (`T.C. SAĞLIK BAKANLIĞI BURSA ŞEHİR HASTANESİ`).
Python'un `str.lower()`'ı Türkçe için yanlıştır: `İ` iki kod noktasına açılır
(`i` + U+0307 birleşen nokta), `I` ise `ı` yerine ASCII `i` üretir. İkisi de
alt-dize aramasını sessizce başarısız kılar.
"""

from __future__ import annotations

# `.lower()` yalnız bu ikisini yanlış yapar; Ç/Ğ/Ö/Ş/Ü zaten doğru katlanır.
_TR_LOWER_MAP = str.maketrans({"İ": "i", "I": "ı"})


def tr_lower(s: str) -> str:
    """Türkçe kurallarına göre küçük harfe çevirir (`İ`→`i`, `I`→`ı`).

    Filtrelerde sorgunun VE verinin her ikisine de uygulanmalıdır; yalnız birine
    uygulamak eşleşmeyi düzeltmez.

    ASCII sabitlerle (parser'ın atadığı `diger`/`isitme` gibi kategori slug'ları)
    karşılaştırma yaparken KULLANMAYIN — orada `tr_lower("DIGER")` == "dığer"
    olur ve slug'a uymaz; düz `.lower()` doğrudur.
    """
    return s.translate(_TR_LOWER_MAP).lower()


def tr_contains(needle: str, haystack: str | None) -> bool:
    """`needle`, `haystack` içinde geçiyor mu — Türkçe-doğru, büyük/küçük harf duyarsız."""
    if not haystack:
        return False
    return tr_lower(needle) in tr_lower(haystack)
